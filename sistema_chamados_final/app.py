from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3, os, re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'ti_prefeitura_2025_secret_key'
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

LOCAIS_ESTOQUE = ['TI', 'Prateleira 1', 'Prateleira 2', 'Prateleira 3', 'Prateleira 4', 'Prateleira 5']

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def log(acao, detalhe=''):
    try:
        conn = get_db()
        conn.execute("INSERT INTO log_acoes (usuario_id,usuario_nome,acao,detalhe,data) VALUES (?,?,?,?,?)",
            (session.get('usuario_id'), session.get('nome'), acao, detalhe, now()))
        conn.commit()
        conn.close()
    except:
        pass

def validar_cpf(cpf):
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for i in range(2):
        soma = sum(int(cpf[j]) * (10 + i - j) for j in range(9 + i))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[9 + i]):
            return False
    return True

def paginar(items, page, per_page=25):
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return items[start:start + per_page], page, total_pages, total

def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*a, **kw)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        if session.get('perfil') != 'admin':
            flash('Acesso restrito a administradores.', 'erro')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return d

def tecnico_required(f):
    @wraps(f)
    def d(*a, **kw):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        if session.get('perfil') not in ('admin', 'tecnico'):
            flash('Acesso restrito a técnicos ou administradores.', 'erro')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return d

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL, cpf TEXT UNIQUE NOT NULL, senha TEXT NOT NULL,
        perfil TEXT NOT NULL DEFAULT 'usuario', setor TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1, criado_em TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS maquinas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tombo TEXT UNIQUE NOT NULL, marca TEXT NOT NULL, modelo TEXT NOT NULL,
        serial TEXT, tipo TEXT NOT NULL, unidade TEXT NOT NULL, setor TEXT NOT NULL,
        situacao TEXT NOT NULL DEFAULT 'ativa', criado_em TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS historico_setor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        maquina_id INTEGER NOT NULL, setor_anterior TEXT, setor_novo TEXT NOT NULL,
        motivo TEXT, data TEXT NOT NULL, usuario_id INTEGER,
        FOREIGN KEY(maquina_id) REFERENCES maquinas(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS pecas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL, categoria TEXT NOT NULL,
        observacao TEXT, criado_em TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        peca_id INTEGER UNIQUE NOT NULL, local TEXT NOT NULL,
        quantidade INTEGER NOT NULL DEFAULT 0, observacao TEXT, criado_em TEXT NOT NULL,
        FOREIGN KEY(peca_id) REFERENCES pecas(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        peca_id INTEGER NOT NULL, tipo TEXT NOT NULL, quantidade INTEGER NOT NULL,
        motivo TEXT NOT NULL, chamado_id INTEGER, usuario_id INTEGER, data TEXT NOT NULL,
        FOREIGN KEY(peca_id) REFERENCES pecas(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS chamados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL, descricao TEXT NOT NULL, setor TEXT NOT NULL,
        maquina_id INTEGER, prioridade TEXT NOT NULL DEFAULT 'media',
        status TEXT NOT NULL DEFAULT 'aberto', solucao TEXT,
        aberto_por INTEGER NOT NULL, tecnico_id INTEGER,
        criado_em TEXT NOT NULL, assumido_em TEXT, concluido_em TEXT,
        FOREIGN KEY(maquina_id) REFERENCES maquinas(id),
        FOREIGN KEY(aberto_por) REFERENCES usuarios(id),
        FOREIGN KEY(tecnico_id) REFERENCES usuarios(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS log_acoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER, usuario_nome TEXT, acao TEXT NOT NULL,
        detalhe TEXT, data TEXT NOT NULL)''')
    c.execute("SELECT id FROM usuarios WHERE cpf='00000000000'")
    if not c.fetchone():
        conn.execute("INSERT INTO usuarios (nome,cpf,senha,perfil,setor,criado_em) VALUES (?,?,?,?,?,?)",
            ('Administrador','00000000000',generate_password_hash('admin123'),'admin','TI',now()))
    conn.commit()
    conn.close()

# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET','POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    erro = None
    if request.method == 'POST':
        cpf   = re.sub(r'\D','', request.form.get('cpf',''))
        senha = request.form.get('senha','').strip()
        conn  = get_db()
        u     = conn.execute("SELECT * FROM usuarios WHERE cpf=? AND ativo=1",(cpf,)).fetchone()
        conn.close()
        if u and check_password_hash(u['senha'], senha):
            session.update({'usuario_id':u['id'],'nome':u['nome'],'perfil':u['perfil'],'setor':u['setor']})
            log('LOGIN', f'Entrou no sistema')
            return redirect(url_for('dashboard'))
        erro = 'CPF ou senha inválidos.'
    return render_template('login.html', erro=erro)

@app.route('/logout')
def logout():
    log('LOGOUT','Saiu do sistema')
    session.clear()
    return redirect(url_for('login'))

# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    stats = {
        'abertos':    conn.execute("SELECT COUNT(*) FROM chamados WHERE status='aberto'").fetchone()[0],
        'andamento':  conn.execute("SELECT COUNT(*) FROM chamados WHERE status='em_andamento'").fetchone()[0],
        'concluidos': conn.execute("SELECT COUNT(*) FROM chamados WHERE status='concluido'").fetchone()[0],
        'maquinas':   conn.execute("SELECT COUNT(*) FROM maquinas WHERE situacao='ativa'").fetchone()[0],
        'pecas_baixo':conn.execute("SELECT COUNT(*) FROM estoque WHERE quantidade <= 2").fetchone()[0],
        'meus':       conn.execute("SELECT COUNT(*) FROM chamados WHERE tecnico_id=? AND status='em_andamento'",(session['usuario_id'],)).fetchone()[0],
    }
    urgentes = conn.execute("""
        SELECT c.*, u.nome as aberto_por_nome, m.tombo, m.modelo
        FROM chamados c LEFT JOIN usuarios u ON c.aberto_por=u.id
        LEFT JOIN maquinas m ON c.maquina_id=m.id
        WHERE c.status IN ('aberto','em_andamento')
        ORDER BY CASE c.prioridade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, c.criado_em LIMIT 10
    """).fetchall()
    pecas_baixo = conn.execute("""SELECT e.*, p.nome, p.categoria FROM estoque e
        JOIN pecas p ON p.id=e.peca_id WHERE e.quantidade<=2 ORDER BY e.quantidade""").fetchall()
    logs_rec    = conn.execute("SELECT * FROM log_acoes ORDER BY data DESC LIMIT 8").fetchall()
    conn.close()
    return render_template('dashboard.html', stats=stats, urgentes=urgentes,
        pecas_baixo=pecas_baixo, logs_rec=logs_rec)

# ── USUÁRIOS ──────────────────────────────────────────────────────────────────

@app.route('/usuarios')
@admin_required
def usuarios():
    q    = request.args.get('q','')
    page = int(request.args.get('page',1))
    conn = get_db()
    if q:
        rows = conn.execute("SELECT * FROM usuarios WHERE nome LIKE ? OR cpf LIKE ? OR setor LIKE ? ORDER BY nome",
            (f'%{q}%',f'%{q}%',f'%{q}%')).fetchall()
    else:
        rows = conn.execute("SELECT * FROM usuarios ORDER BY nome").fetchall()
    conn.close()
    items, page, total_pages, total = paginar(rows, page)
    return render_template('usuarios.html', usuarios=items, q=q, page=page, total_pages=total_pages, total=total)

@app.route('/usuarios/novo', methods=['GET','POST'])
@admin_required
def usuario_novo():
    form = {}
    if request.method == 'POST':
        form   = dict(request.form)
        nome   = request.form.get('nome','').strip()
        cpf    = re.sub(r'\D','', request.form.get('cpf',''))
        senha  = request.form.get('senha','').strip()
        conf   = request.form.get('confirmar_senha','').strip()
        perfil = request.form.get('perfil','')
        setor  = request.form.get('setor','').strip()
        if not all([nome,cpf,senha,conf,perfil,setor]):
            flash('Preencha todos os campos obrigatórios.','erro')
            return render_template('usuario_form.html', usuario=None, form=form)
        if not validar_cpf(cpf):
            flash('CPF inválido. Verifique os dígitos.','erro')
            return render_template('usuario_form.html', usuario=None, form=form)
        if senha != conf:
            flash('As senhas não coincidem.','erro')
            return render_template('usuario_form.html', usuario=None, form=form)
        if len(senha) < 6:
            flash('A senha deve ter no mínimo 6 caracteres.','erro')
            return render_template('usuario_form.html', usuario=None, form=form)
        try:
            conn = get_db()
            conn.execute("INSERT INTO usuarios (nome,cpf,senha,perfil,setor,criado_em) VALUES (?,?,?,?,?,?)",
                (nome,cpf,generate_password_hash(senha),perfil,setor,now()))
            conn.commit()
            conn.close()
            log('USUARIO_CRIADO', f'{nome} ({cpf})')
            flash('Usuário cadastrado com sucesso!','ok')
            return redirect(url_for('usuarios'))
        except sqlite3.IntegrityError:
            flash('CPF já cadastrado no sistema.','erro')
    return render_template('usuario_form.html', usuario=None, form=form)

@app.route('/usuarios/<int:uid>/editar', methods=['GET','POST'])
@admin_required
def usuario_editar(uid):
    conn = get_db()
    u    = conn.execute("SELECT * FROM usuarios WHERE id=?",(uid,)).fetchone()
    conn.close()
    if not u:
        flash('Usuário não encontrado.','erro')
        return redirect(url_for('usuarios'))
    form = dict(u) if request.method=='GET' else dict(request.form)
    if request.method == 'POST':
        nome   = form.get('nome','').strip()
        perfil = form.get('perfil','')
        setor  = form.get('setor','').strip()
        ativo  = 1 if form.get('ativo') else 0
        nova   = form.get('nova_senha','').strip()
        conf   = form.get('confirmar_nova_senha','').strip()
        if not all([nome,perfil,setor]):
            flash('Preencha todos os campos obrigatórios.','erro')
            return render_template('usuario_form.html', usuario=u, form=form)
        if nova:
            if nova != conf:
                flash('As senhas não coincidem.','erro')
                return render_template('usuario_form.html', usuario=u, form=form)
            if len(nova) < 6:
                flash('Mínimo 6 caracteres para a senha.','erro')
                return render_template('usuario_form.html', usuario=u, form=form)
        conn = get_db()
        if nova:
            conn.execute("UPDATE usuarios SET nome=?,perfil=?,setor=?,ativo=?,senha=? WHERE id=?",
                (nome,perfil,setor,ativo,generate_password_hash(nova),uid))
        else:
            conn.execute("UPDATE usuarios SET nome=?,perfil=?,setor=?,ativo=? WHERE id=?",
                (nome,perfil,setor,ativo,uid))
        conn.commit()
        conn.close()
        log('USUARIO_EDITADO', f'{nome} (id={uid})')
        flash('Usuário atualizado!','ok')
        return redirect(url_for('usuarios'))
    return render_template('usuario_form.html', usuario=u, form=form)

@app.route('/usuarios/<int:uid>/ativar', methods=['POST'])
@admin_required
def usuario_ativar(uid):
    conn = get_db()
    u = conn.execute("SELECT nome FROM usuarios WHERE id=?",(uid,)).fetchone()
    conn.execute("UPDATE usuarios SET ativo=1 WHERE id=?",(uid,))
    conn.commit()
    conn.close()
    log('USUARIO_ATIVADO', f'{u["nome"]} reativado')
    flash('Usuário reativado com sucesso!','ok')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/<int:uid>/desativar', methods=['POST'])
@admin_required
def usuario_desativar(uid):
    if uid == session['usuario_id']:
        flash('Você não pode desativar sua própria conta.','erro')
        return redirect(url_for('usuarios'))
    conn = get_db()
    u = conn.execute("SELECT nome FROM usuarios WHERE id=?",(uid,)).fetchone()
    conn.execute("UPDATE usuarios SET ativo=0 WHERE id=?",(uid,))
    conn.commit()
    conn.close()
    log('USUARIO_DESATIVADO', f'{u["nome"]} desativado')
    flash('Usuário desativado!','ok')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/<int:uid>/excluir', methods=['POST'])
@admin_required
def usuario_excluir(uid):
    if uid == session['usuario_id']:
        flash('Você não pode excluir sua própria conta.','erro')
        return redirect(url_for('usuarios'))
    conn = get_db()
    u = conn.execute("SELECT nome FROM usuarios WHERE id=?",(uid,)).fetchone()
    qtd = conn.execute("SELECT COUNT(*) FROM chamados WHERE aberto_por=? OR tecnico_id=?",(uid,uid)).fetchone()[0]
    if qtd > 0:
        conn.close()
        flash(f'Não é possível excluir: {qtd} chamado(s) vinculado(s). Use "Desativar" em vez disso.','erro')
        return redirect(url_for('usuarios'))
    conn.execute("DELETE FROM usuarios WHERE id=?",(uid,))
    conn.commit()
    conn.close()
    log('USUARIO_EXCLUIDO', f'{u["nome"]} excluído permanentemente')
    flash('Usuário excluído!','ok')
    return redirect(url_for('usuarios'))

# ── MÁQUINAS ──────────────────────────────────────────────────────────────────

@app.route('/maquinas')
@login_required
def maquinas():
    q    = request.args.get('q','')
    sit  = request.args.get('situacao','')
    page = int(request.args.get('page',1))
    conn = get_db()
    sql  = "SELECT * FROM maquinas WHERE 1=1"
    p    = []
    if q:
        sql += " AND (tombo LIKE ? OR marca LIKE ? OR modelo LIKE ? OR setor LIKE ? OR serial LIKE ? OR unidade LIKE ?)"
        p.extend([f'%{q}%']*6)
    if sit:
        sql += " AND situacao=?"
        p.append(sit)
    rows = conn.execute(sql+' ORDER BY tombo', p).fetchall()
    conn.close()
    items, page, total_pages, total = paginar(rows, page)
    return render_template('maquinas.html', maquinas=items, q=q, situacao=sit,
        page=page, total_pages=total_pages, total=total)

@app.route('/maquinas/nova', methods=['GET','POST'])
@tecnico_required
def maquina_nova():
    form = {}
    if request.method == 'POST':
        form    = dict(request.form)
        tombo   = form.get('tombo','').strip()
        marca   = form.get('marca','').strip()
        modelo  = form.get('modelo','').strip()
        serial  = form.get('serial','').strip()
        tipo    = form.get('tipo','')
        unidade = form.get('unidade','').strip()
        setor   = form.get('setor','').strip()
        sit     = form.get('situacao','ativa')
        if not all([tombo,marca,modelo,tipo,unidade,setor]):
            flash('Preencha todos os campos obrigatórios.','erro')
            return render_template('maquina_form.html', maquina=None, form=form)
        try:
            conn = get_db()
            conn.execute("INSERT INTO maquinas (tombo,marca,modelo,serial,tipo,unidade,setor,situacao,criado_em) VALUES (?,?,?,?,?,?,?,?,?)",
                (tombo,marca,modelo,serial,tipo,unidade,setor,sit,now()))
            conn.commit()
            conn.close()
            log('MAQUINA_CRIADA', f'Tombo {tombo}')
            flash('Máquina cadastrada!','ok')
            return redirect(url_for('maquinas'))
        except sqlite3.IntegrityError:
            flash('Número de tombo já cadastrado.','erro')
    return render_template('maquina_form.html', maquina=None, form=form)

@app.route('/maquinas/<int:mid>/editar', methods=['GET','POST'])
@tecnico_required
def maquina_editar(mid):
    conn = get_db()
    m    = conn.execute("SELECT * FROM maquinas WHERE id=?",(mid,)).fetchone()
    conn.close()
    if not m:
        flash('Máquina não encontrada.','erro')
        return redirect(url_for('maquinas'))
    form = dict(m) if request.method=='GET' else dict(request.form)
    if request.method == 'POST':
        marca   = form.get('marca','').strip()
        modelo  = form.get('modelo','').strip()
        serial  = form.get('serial','').strip()
        tipo    = form.get('tipo','')
        unidade = form.get('unidade','').strip()
        setor_n = form.get('setor','').strip()
        sit     = form.get('situacao','')
        motivo  = form.get('motivo_troca','').strip()
        if not all([marca,modelo,tipo,unidade,setor_n]):
            flash('Preencha todos os campos obrigatórios.','erro')
            return render_template('maquina_form.html', maquina=m, form=form)
        conn = get_db()
        if setor_n != m['setor']:
            conn.execute("INSERT INTO historico_setor (maquina_id,setor_anterior,setor_novo,motivo,data,usuario_id) VALUES (?,?,?,?,?,?)",
                (mid,m['setor'],setor_n,motivo,now(),session['usuario_id']))
        conn.execute("UPDATE maquinas SET marca=?,modelo=?,serial=?,tipo=?,unidade=?,setor=?,situacao=? WHERE id=?",
            (marca,modelo,serial,tipo,unidade,setor_n,sit,mid))
        conn.commit()
        conn.close()
        log('MAQUINA_EDITADA', f'Tombo {m["tombo"]}')
        flash('Máquina atualizada!','ok')
        return redirect(url_for('maquinas'))
    return render_template('maquina_form.html', maquina=m, form=form)

@app.route('/maquinas/<int:mid>/historico')
@login_required
def maquina_historico(mid):
    conn = get_db()
    m    = conn.execute("SELECT * FROM maquinas WHERE id=?",(mid,)).fetchone()
    hist = conn.execute("""SELECT h.*, u.nome as usuario_nome FROM historico_setor h
        LEFT JOIN usuarios u ON h.usuario_id=u.id WHERE h.maquina_id=? ORDER BY h.data DESC""",(mid,)).fetchall()
    conn.close()
    return render_template('maquina_historico.html', maquina=m, historico=hist)

@app.route('/maquinas/<int:mid>/excluir', methods=['POST'])
@admin_required
def maquina_excluir(mid):
    conn = get_db()
    m    = conn.execute("SELECT * FROM maquinas WHERE id=?",(mid,)).fetchone()
    qtd  = conn.execute("SELECT COUNT(*) FROM chamados WHERE maquina_id=?",(mid,)).fetchone()[0]
    if qtd > 0:
        conn.close()
        flash(f'Não é possível excluir: {qtd} chamado(s) vinculado(s).','erro')
        return redirect(url_for('maquinas'))
    conn.execute("DELETE FROM historico_setor WHERE maquina_id=?",(mid,))
    conn.execute("DELETE FROM maquinas WHERE id=?",(mid,))
    conn.commit()
    conn.close()
    log('MAQUINA_EXCLUIDA', f'Tombo {m["tombo"]}')
    flash('Máquina excluída!','ok')
    return redirect(url_for('maquinas'))

@app.route('/api/maquina_por_tombo')
@login_required
def api_maquina_por_tombo():
    tombo = request.args.get('tombo','').strip()
    conn  = get_db()
    m     = conn.execute("SELECT * FROM maquinas WHERE tombo=?",(tombo,)).fetchone()
    conn.close()
    if m:
        return jsonify({'id':m['id'],'modelo':m['modelo'],'marca':m['marca'],'setor':m['setor'],'situacao':m['situacao']})
    return jsonify({'erro':'Máquina não encontrada'}), 404

# ── PEÇAS (cadastro) ─────────────────────────────────────────────────────────

@app.route('/pecas')
@login_required
def pecas():
    q    = request.args.get('q','')
    page = int(request.args.get('page',1))
    conn = get_db()
    if q:
        rows = conn.execute("""SELECT p.*, e.local as estoque_local, COALESCE(e.quantidade,0) as estoque_quantidade
            FROM pecas p LEFT JOIN estoque e ON e.peca_id=p.id
            WHERE p.nome LIKE ? OR p.categoria LIKE ? ORDER BY p.nome""",
            (f'%{q}%',f'%{q}%')).fetchall()
    else:
        rows = conn.execute("""SELECT p.*, e.local as estoque_local, COALESCE(e.quantidade,0) as estoque_quantidade
            FROM pecas p LEFT JOIN estoque e ON e.peca_id=p.id ORDER BY p.nome""").fetchall()
    conn.close()
    items, page, total_pages, total = paginar(rows, page)
    return render_template('pecas.html', pecas=items, q=q, page=page, total_pages=total_pages, total=total)

@app.route('/pecas/nova', methods=['GET','POST'])
@tecnico_required
def peca_nova():
    form = {}
    if request.method == 'POST':
        form  = dict(request.form)
        nome  = form.get('nome','').strip()
        cat   = form.get('categoria','').strip()
        obs   = form.get('observacao','').strip()
        if not all([nome,cat]):
            flash('Preencha todos os campos obrigatórios.','erro')
            return render_template('peca_form.html', peca=None, form=form)
        conn = get_db()
        conn.execute("INSERT INTO pecas (nome,categoria,observacao,criado_em) VALUES (?,?,?,?)",
            (nome,cat,obs,now()))
        conn.commit()
        conn.close()
        log('PECA_CRIADA', f'{nome}')
        flash('Peça cadastrada! Agora informe o local e a quantidade na tela de Estoque.','ok')
        return redirect(url_for('pecas'))
    return render_template('peca_form.html', peca=None, form=form)

@app.route('/pecas/<int:pid>/editar', methods=['GET','POST'])
@tecnico_required
def peca_editar(pid):
    conn = get_db()
    p    = conn.execute("SELECT * FROM pecas WHERE id=?",(pid,)).fetchone()
    conn.close()
    if not p:
        flash('Peça não encontrada.','erro')
        return redirect(url_for('pecas'))
    form = dict(p) if request.method=='GET' else dict(request.form)
    if request.method == 'POST':
        nome = form.get('nome','').strip()
        cat  = form.get('categoria','').strip()
        obs  = form.get('observacao','').strip()
        if not all([nome,cat]):
            flash('Preencha todos os campos obrigatórios.','erro')
            return render_template('peca_form.html', peca=p, form=form)
        conn = get_db()
        conn.execute("UPDATE pecas SET nome=?,categoria=?,observacao=? WHERE id=?",(nome,cat,obs,pid))
        conn.commit()
        conn.close()
        log('PECA_EDITADA', f'{nome}')
        flash('Peça atualizada!','ok')
        return redirect(url_for('pecas'))
    return render_template('peca_form.html', peca=p, form=form)

@app.route('/pecas/<int:pid>/historico')
@login_required
def peca_historico(pid):
    conn = get_db()
    p    = conn.execute("""SELECT p.*, e.local as estoque_local, e.quantidade as estoque_quantidade
        FROM pecas p LEFT JOIN estoque e ON e.peca_id=p.id WHERE p.id=?""",(pid,)).fetchone()
    hist = conn.execute("""SELECT m.*, u.nome as usuario_nome FROM movimentacoes_estoque m
        LEFT JOIN usuarios u ON m.usuario_id=u.id WHERE m.peca_id=? ORDER BY m.data DESC""",(pid,)).fetchall()
    conn.close()
    return render_template('peca_historico.html', peca=p, historico=hist)

@app.route('/pecas/<int:pid>/excluir', methods=['POST'])
@admin_required
def peca_excluir(pid):
    conn = get_db()
    p = conn.execute("SELECT nome FROM pecas WHERE id=?",(pid,)).fetchone()
    conn.execute("DELETE FROM movimentacoes_estoque WHERE peca_id=?",(pid,))
    conn.execute("DELETE FROM estoque WHERE peca_id=?",(pid,))
    conn.execute("DELETE FROM pecas WHERE id=?",(pid,))
    conn.commit()
    conn.close()
    log('PECA_EXCLUIDA', f'{p["nome"]}')
    flash('Peça excluída!','ok')
    return redirect(url_for('pecas'))

@app.route('/api/pecas')
@login_required
def api_pecas():
    conn  = get_db()
    rows  = conn.execute("""SELECT p.id, p.nome, p.categoria, COALESCE(e.quantidade,0) as quantidade
        FROM pecas p LEFT JOIN estoque e ON e.peca_id=p.id ORDER BY p.nome""").fetchall()
    conn.close()
    return jsonify([dict(p) for p in rows])

# ── ESTOQUE (local e quantidade) ────────────────────────────────────────────

@app.route('/estoque')
@login_required
def estoque():
    q    = request.args.get('q','')
    page = int(request.args.get('page',1))
    conn = get_db()
    if q:
        rows = conn.execute("""SELECT e.*, p.nome as peca_nome, p.categoria as peca_categoria
            FROM estoque e JOIN pecas p ON p.id=e.peca_id
            WHERE p.nome LIKE ? OR p.categoria LIKE ? OR e.local LIKE ? ORDER BY p.nome""",
            (f'%{q}%',f'%{q}%',f'%{q}%')).fetchall()
    else:
        rows = conn.execute("""SELECT e.*, p.nome as peca_nome, p.categoria as peca_categoria
            FROM estoque e JOIN pecas p ON p.id=e.peca_id ORDER BY p.nome""").fetchall()
    conn.close()
    items, page, total_pages, total = paginar(rows, page)
    return render_template('estoque.html', registros=items, q=q, page=page, total_pages=total_pages, total=total)

@app.route('/estoque/novo', methods=['GET','POST'])
@tecnico_required
def estoque_novo():
    conn  = get_db()
    todas = conn.execute("""SELECT p.* FROM pecas p
        WHERE p.id NOT IN (SELECT peca_id FROM estoque) ORDER BY p.nome""").fetchall()
    conn.close()
    form = {}
    if request.method == 'POST':
        form  = dict(request.form)
        pid   = form.get('peca_id','')
        local = form.get('local','').strip()
        qtd   = form.get('quantidade','0')
        obs   = form.get('observacao','').strip()
        if not all([pid, local]) or local not in LOCAIS_ESTOQUE:
            flash('Selecione a peça e um local válido.','erro')
            return render_template('estoque_form.html', registro=None, form=form, pecas=todas, locais=LOCAIS_ESTOQUE)
        try: qtd = max(0, int(qtd))
        except: qtd = 0
        conn = get_db()
        existente = conn.execute("SELECT id FROM estoque WHERE peca_id=?",(pid,)).fetchone()
        if existente:
            conn.close()
            flash('Esta peça já possui um registro de estoque. Edite o registro existente.','erro')
            return render_template('estoque_form.html', registro=None, form=form, pecas=todas, locais=LOCAIS_ESTOQUE)
        peca = conn.execute("SELECT nome FROM pecas WHERE id=?",(pid,)).fetchone()
        conn.execute("INSERT INTO estoque (peca_id,local,quantidade,observacao,criado_em) VALUES (?,?,?,?,?)",
            (pid,local,qtd,obs,now()))
        if qtd > 0:
            conn.execute("INSERT INTO movimentacoes_estoque (peca_id,tipo,quantidade,motivo,chamado_id,usuario_id,data) VALUES (?,?,?,?,?,?,?)",
                (pid,'entrada',qtd,'Estoque inicial',None,session['usuario_id'],now()))
        conn.commit()
        conn.close()
        log('ESTOQUE_CRIADO', f'{peca["nome"]} — {local} ({qtd})')
        flash('Estoque cadastrado!','ok')
        return redirect(url_for('estoque'))
    return render_template('estoque_form.html', registro=None, form=form, pecas=todas, locais=LOCAIS_ESTOQUE)

@app.route('/estoque/<int:eid>/editar', methods=['GET','POST'])
@tecnico_required
def estoque_editar(eid):
    conn = get_db()
    reg  = conn.execute("""SELECT e.*, p.nome as peca_nome FROM estoque e
        JOIN pecas p ON p.id=e.peca_id WHERE e.id=?""",(eid,)).fetchone()
    conn.close()
    if not reg:
        flash('Registro de estoque não encontrado.','erro')
        return redirect(url_for('estoque'))
    form = dict(reg) if request.method=='GET' else dict(request.form)
    if request.method == 'POST':
        local = form.get('local','').strip()
        obs   = form.get('observacao','').strip()
        if local not in LOCAIS_ESTOQUE:
            flash('Selecione um local válido.','erro')
            return render_template('estoque_form.html', registro=reg, form=form, pecas=None, locais=LOCAIS_ESTOQUE)
        conn = get_db()
        conn.execute("UPDATE estoque SET local=?,observacao=? WHERE id=?",(local,obs,eid))
        conn.commit()
        conn.close()
        log('ESTOQUE_EDITADO', f'{reg["peca_nome"]} — {local}')
        flash('Estoque atualizado!','ok')
        return redirect(url_for('estoque'))
    return render_template('estoque_form.html', registro=reg, form=form, pecas=None, locais=LOCAIS_ESTOQUE)

@app.route('/estoque/<int:eid>/movimentar', methods=['GET','POST'])
@tecnico_required
def estoque_movimentar(eid):
    conn = get_db()
    reg  = conn.execute("""SELECT e.*, p.nome as peca_nome FROM estoque e
        JOIN pecas p ON p.id=e.peca_id WHERE e.id=?""",(eid,)).fetchone()
    conn.close()
    if not reg:
        flash('Registro de estoque não encontrado.','erro')
        return redirect(url_for('estoque'))
    if request.method == 'POST':
        tipo   = request.form.get('tipo','')
        motivo = request.form.get('motivo','').strip()
        try:
            qtd = int(request.form.get('quantidade',0))
            if qtd <= 0: raise ValueError
        except:
            flash('Quantidade inválida.','erro')
            return render_template('estoque_movimentar.html', registro=reg)
        if not motivo:
            flash('Informe o motivo.','erro')
            return render_template('estoque_movimentar.html', registro=reg)
        if tipo == 'saida' and reg['quantidade'] < qtd:
            flash(f'Estoque insuficiente. Disponível: {reg["quantidade"]}.','erro')
            return render_template('estoque_movimentar.html', registro=reg)
        nova = reg['quantidade'] + qtd if tipo=='entrada' else reg['quantidade'] - qtd
        conn = get_db()
        conn.execute("UPDATE estoque SET quantidade=? WHERE id=?",(nova,eid))
        conn.execute("INSERT INTO movimentacoes_estoque (peca_id,tipo,quantidade,motivo,chamado_id,usuario_id,data) VALUES (?,?,?,?,?,?,?)",
            (reg['peca_id'],tipo,qtd,motivo,request.form.get('chamado_id') or None,session['usuario_id'],now()))
        conn.commit()
        conn.close()
        log('ESTOQUE_MOV', f'{tipo.upper()} {qtd}x {reg["peca_nome"]}')
        flash(f'Movimentação registrada! Novo estoque: {nova}.','ok')
        return redirect(url_for('estoque'))
    return render_template('estoque_movimentar.html', registro=reg)

@app.route('/estoque/<int:eid>/excluir', methods=['POST'])
@admin_required
def estoque_excluir(eid):
    conn = get_db()
    reg = conn.execute("""SELECT e.*, p.nome as peca_nome FROM estoque e
        JOIN pecas p ON p.id=e.peca_id WHERE e.id=?""",(eid,)).fetchone()
    if reg:
        conn.execute("DELETE FROM estoque WHERE id=?",(eid,))
        conn.commit()
        log('ESTOQUE_EXCLUIDO', f'{reg["peca_nome"]} — {reg["local"]}')
    conn.close()
    flash('Registro de estoque excluído!','ok')
    return redirect(url_for('estoque'))

# ── CHAMADOS ──────────────────────────────────────────────────────────────────

@app.route('/chamados')
@login_required
def chamados():
    q     = request.args.get('q','')
    st    = request.args.get('status','')
    pri   = request.args.get('prioridade','')
    meus  = request.args.get('meus','')
    page  = int(request.args.get('page',1))
    conn  = get_db()
    sql   = """SELECT c.*, u.nome as aberto_por_nome, t.nome as tecnico_nome, m.tombo, m.modelo
               FROM chamados c LEFT JOIN usuarios u ON c.aberto_por=u.id
               LEFT JOIN usuarios t ON c.tecnico_id=t.id
               LEFT JOIN maquinas m ON c.maquina_id=m.id WHERE 1=1"""
    p = []
    if q:
        sql += " AND (c.titulo LIKE ? OR c.setor LIKE ? OR m.tombo LIKE ?)"
        p.extend([f'%{q}%']*3)
    if st:
        sql += " AND c.status=?"
        p.append(st)
    if pri:
        sql += " AND c.prioridade=?"
        p.append(pri)
    if meus:
        sql += " AND c.tecnico_id=?"
        p.append(session['usuario_id'])
    sql += " ORDER BY CASE c.prioridade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, c.criado_em DESC"
    rows = conn.execute(sql, p).fetchall()
    conn.close()
    items, page, total_pages, total = paginar(rows, page)
    return render_template('chamados.html', chamados=items, q=q, status=st,
        prioridade=pri, meus=meus, page=page, total_pages=total_pages, total=total)

@app.route('/chamados/novo', methods=['GET','POST'])
@login_required
def chamado_novo():
    form = {}
    if request.method == 'POST':
        form  = dict(request.form)
        titulo    = form.get('titulo','').strip()
        descricao = form.get('descricao','').strip()
        setor     = form.get('setor','').strip()
        tombo     = form.get('tombo','').strip()
        prioridade= form.get('prioridade','media')
        if not all([titulo,descricao,setor,prioridade]):
            flash('Preencha todos os campos obrigatórios.','erro')
            return render_template('chamado_form.html', form=form)
        conn = get_db()
        maquina_id = None
        if tombo:
            m = conn.execute("SELECT id FROM maquinas WHERE tombo=?",(tombo,)).fetchone()
            if not m:
                conn.close()
                flash('Tombo não encontrado no sistema.','erro')
                return render_template('chamado_form.html', form=form)
            maquina_id = m['id']
        conn.execute("INSERT INTO chamados (titulo,descricao,setor,maquina_id,prioridade,status,aberto_por,criado_em) VALUES (?,?,?,?,?,?,?,?)",
            (titulo,descricao,setor,maquina_id,prioridade,'aberto',session['usuario_id'],now()))
        conn.commit()
        conn.close()
        log('CHAMADO_ABERTO', f'"{titulo}" — {setor}')
        flash('Chamado aberto com sucesso!','ok')
        return redirect(url_for('chamados'))
    return render_template('chamado_form.html', form=form)

@app.route('/chamados/<int:cid>')
@login_required
def chamado_ver(cid):
    conn = get_db()
    c = conn.execute("""SELECT c.*, u.nome as aberto_por_nome, t.nome as tecnico_nome,
        m.tombo, m.modelo, m.marca, m.setor as maquina_setor, m.situacao as maquina_situacao, m.id as mid
        FROM chamados c LEFT JOIN usuarios u ON c.aberto_por=u.id
        LEFT JOIN usuarios t ON c.tecnico_id=t.id
        LEFT JOIN maquinas m ON c.maquina_id=m.id WHERE c.id=?""",(cid,)).fetchone()
    if not c:
        conn.close()
        flash('Chamado não encontrado.','erro')
        return redirect(url_for('chamados'))
    pecas_usadas = conn.execute("""SELECT me.*, p.nome as peca_nome FROM movimentacoes_estoque me
        LEFT JOIN pecas p ON me.peca_id=p.id WHERE me.chamado_id=?""",(cid,)).fetchall()
    conn.close()
    return render_template('chamado_ver.html', chamado=c, pecas_usadas=pecas_usadas)

@app.route('/chamados/<int:cid>/assumir', methods=['POST'])
@tecnico_required
def chamado_assumir(cid):
    conn = get_db()
    c = conn.execute("SELECT * FROM chamados WHERE id=?",(cid,)).fetchone()
    if not c or c['status'] != 'aberto':
        conn.close()
        flash('Chamado não disponível para assumir.','erro')
        return redirect(url_for('chamados'))
    conn.execute("UPDATE chamados SET status='em_andamento',tecnico_id=?,assumido_em=? WHERE id=?",
        (session['usuario_id'],now(),cid))
    conn.commit()
    conn.close()
    log('CHAMADO_ASSUMIDO', f'Chamado #{cid}')
    flash('Chamado assumido!','ok')
    return redirect(url_for('chamado_ver', cid=cid))

@app.route('/chamados/<int:cid>/reabrir', methods=['POST'])
@tecnico_required
def chamado_reabrir(cid):
    conn = get_db()
    c = conn.execute("SELECT * FROM chamados WHERE id=?",(cid,)).fetchone()
    if not c or c['status'] != 'concluido':
        conn.close()
        flash('Apenas chamados concluídos podem ser reabertos.','erro')
        return redirect(url_for('chamado_ver', cid=cid))
    conn.execute("UPDATE chamados SET status='aberto',tecnico_id=NULL,solucao=NULL,assumido_em=NULL,concluido_em=NULL WHERE id=?",
        (cid,))
    conn.commit()
    conn.close()
    log('CHAMADO_REABERTO', f'Chamado #{cid} reaberto')
    flash('Chamado reaberto!','ok')
    return redirect(url_for('chamado_ver', cid=cid))

@app.route('/chamados/<int:cid>/fechar', methods=['GET','POST'])
@tecnico_required
def chamado_fechar(cid):
    conn = get_db()
    c = conn.execute("""SELECT c.*, m.tombo, m.modelo FROM chamados c
        LEFT JOIN maquinas m ON c.maquina_id=m.id WHERE c.id=?""",(cid,)).fetchone()
    if not c:
        conn.close()
        flash('Chamado não encontrado.','erro')
        return redirect(url_for('chamados'))
    if c['status'] == 'concluido':
        conn.close()
        flash('Chamado já está concluído.','erro')
        return redirect(url_for('chamado_ver', cid=cid))
    todas_pecas = conn.execute("""SELECT p.id, p.nome, p.categoria, COALESCE(e.quantidade,0) as quantidade
        FROM pecas p LEFT JOIN estoque e ON e.peca_id=p.id ORDER BY p.nome""").fetchall()
    conn.close()

    if request.method == 'POST':
        solucao   = request.form.get('solucao','').strip()
        dar_baixa = request.form.get('dar_baixa_maquina','')
        peca_ids  = request.form.getlist('peca_id[]')
        peca_qtds = request.form.getlist('peca_qtd[]')

        if not solucao:
            flash('Informe a solução aplicada.','erro')
            return render_template('chamado_fechar.html', chamado=c, pecas=todas_pecas)

        # Validar estoque antes de qualquer alteração
        conn = get_db()
        erros = []
        itens_ok = []
        for pid_s, qtd_s in zip(peca_ids, peca_qtds):
            try:
                pid = int(pid_s); qtd = int(qtd_s)
                if qtd <= 0: continue
            except:
                continue
            p = conn.execute("SELECT p.nome, COALESCE(e.quantidade,0) as quantidade FROM pecas p LEFT JOIN estoque e ON e.peca_id=p.id WHERE p.id=?",(pid,)).fetchone()
            if not p: continue
            if p['quantidade'] < qtd:
                erros.append(f'"{p["nome"]}": disponível {p["quantidade"]}, solicitado {qtd}')
            else:
                itens_ok.append((pid, qtd, p['nome']))

        if erros:
            conn.close()
            flash('Estoque insuficiente para: ' + ' | '.join(erros),'erro')
            return render_template('chamado_fechar.html', chamado=c, pecas=todas_pecas)

        # Dar baixa nas peças
        for pid, qtd, pnome in itens_ok:
            conn.execute("UPDATE estoque SET quantidade=quantidade-? WHERE peca_id=?",(qtd,pid))
            conn.execute("INSERT INTO movimentacoes_estoque (peca_id,tipo,quantidade,motivo,chamado_id,usuario_id,data) VALUES (?,?,?,?,?,?,?)",
                (pid,'saida',qtd,f'Manutenção — Chamado #{cid}',cid,session['usuario_id'],now()))

        # Fechar chamado
        tecnico_id = c['tecnico_id'] or session['usuario_id']
        conn.execute("UPDATE chamados SET status='concluido',solucao=?,tecnico_id=?,concluido_em=? WHERE id=?",
            (solucao,tecnico_id,now(),cid))

        # Baixar máquina se marcado
        if dar_baixa and c['maquina_id']:
            conn.execute("UPDATE maquinas SET situacao='baixada' WHERE id=?",(c['maquina_id'],))
            conn.execute("INSERT INTO historico_setor (maquina_id,setor_anterior,setor_novo,motivo,data,usuario_id) VALUES (?,?,?,?,?,?)",
                (c['maquina_id'],None,'DESCARTE',f'Baixa via chamado #{cid}',now(),session['usuario_id']))
            log('MAQUINA_BAIXADA', f'Tombo {c["tombo"]} via chamado #{cid}')

        conn.commit()
        conn.close()
        log('CHAMADO_FECHADO', f'Chamado #{cid} — {len(itens_ok)} peça(s) usada(s)')
        flash('Chamado encerrado com sucesso!','ok')
        return redirect(url_for('chamados'))

    return render_template('chamado_fechar.html', chamado=c, pecas=todas_pecas)

@app.route('/chamados/<int:cid>/excluir', methods=['POST'])
@admin_required
def chamado_excluir(cid):
    conn = get_db()
    conn.execute("DELETE FROM chamados WHERE id=?",(cid,))
    conn.commit()
    conn.close()
    log('CHAMADO_EXCLUIDO', f'Chamado #{cid}')
    flash('Chamado excluído!','ok')
    return redirect(url_for('chamados'))

# ── RELATÓRIOS ────────────────────────────────────────────────────────────────

@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

@app.route('/relatorios/abertos')
@login_required
def rel_abertos():
    conn = get_db()
    rows = conn.execute("""SELECT c.*, u.nome as aberto_por_nome, m.tombo, m.modelo
        FROM chamados c LEFT JOIN usuarios u ON c.aberto_por=u.id
        LEFT JOIN maquinas m ON c.maquina_id=m.id WHERE c.status='aberto'
        ORDER BY CASE c.prioridade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END""").fetchall()
    conn.close()
    return render_template('relatorio_lista.html', chamados=rows, titulo='Chamados Abertos')

@app.route('/relatorios/concluidos')
@login_required
def rel_concluidos():
    conn = get_db()
    rows = conn.execute("""SELECT c.*, u.nome as aberto_por_nome, t.nome as tecnico_nome, m.tombo
        FROM chamados c LEFT JOIN usuarios u ON c.aberto_por=u.id
        LEFT JOIN usuarios t ON c.tecnico_id=t.id
        LEFT JOIN maquinas m ON c.maquina_id=m.id WHERE c.status='concluido'
        ORDER BY c.concluido_em DESC""").fetchall()
    conn.close()
    return render_template('relatorio_lista.html', chamados=rows, titulo='Chamados Concluídos')

@app.route('/relatorios/por_tecnico')
@login_required
def rel_por_tecnico():
    conn = get_db()
    rows = conn.execute("""SELECT t.nome as tecnico_nome, COUNT(*) as total,
        SUM(CASE WHEN c.status='concluido' THEN 1 ELSE 0 END) as concluidos,
        SUM(CASE WHEN c.status='em_andamento' THEN 1 ELSE 0 END) as em_andamento
        FROM chamados c LEFT JOIN usuarios t ON c.tecnico_id=t.id
        WHERE c.tecnico_id IS NOT NULL GROUP BY c.tecnico_id ORDER BY total DESC""").fetchall()
    conn.close()
    return render_template('relatorio_tecnico.html', dados=rows)

@app.route('/relatorios/por_periodo')
@login_required
def rel_por_periodo():
    ini = request.args.get('data_ini','')
    fim = request.args.get('data_fim','')
    chamados, totais = [], {}
    if ini and fim:
        conn = get_db()
        chamados = conn.execute("""SELECT c.*, u.nome as aberto_por_nome, t.nome as tecnico_nome, m.tombo
            FROM chamados c LEFT JOIN usuarios u ON c.aberto_por=u.id
            LEFT JOIN usuarios t ON c.tecnico_id=t.id
            LEFT JOIN maquinas m ON c.maquina_id=m.id
            WHERE DATE(c.criado_em) BETWEEN ? AND ? ORDER BY c.criado_em DESC""",(ini,fim)).fetchall()
        conn.close()
        totais = {
            'total':     len(chamados),
            'abertos':   sum(1 for x in chamados if x['status']=='aberto'),
            'andamento': sum(1 for x in chamados if x['status']=='em_andamento'),
            'concluidos':sum(1 for x in chamados if x['status']=='concluido'),
            'alta':  sum(1 for x in chamados if x['prioridade']=='alta'),
            'media': sum(1 for x in chamados if x['prioridade']=='media'),
            'baixa': sum(1 for x in chamados if x['prioridade']=='baixa'),
        }
    return render_template('relatorio_periodo.html', chamados=chamados,
        data_ini=ini, data_fim=fim, totais=totais)

@app.route('/logs')
@admin_required
def logs():
    page = int(request.args.get('page',1))
    conn = get_db()
    rows = conn.execute("SELECT * FROM log_acoes ORDER BY data DESC").fetchall()
    conn.close()
    items, page, total_pages, total = paginar(rows, page, 50)
    return render_template('logs.html', logs=items, page=page, total_pages=total_pages, total=total)

if __name__ == '__main__':
    init_db()
    print("="*50)
    print("SISTEMA TI PREFEITURA — http://localhost:5000")
    print("Login: CPF 00000000000 / Senha: admin123")
    print("="*50)
    app.run(debug=False, host='0.0.0.0', port=5000)
