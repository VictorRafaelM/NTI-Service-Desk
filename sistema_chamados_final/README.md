# Sistema de Controle de Chamados - TI Prefeitura
## PMVCA - Secretaria Municipal de Saúde

Sistema local para controle de chamados de suporte técnico, patrimônio (máquinas), estoque de peças e relatórios do setor de TI.

---

## Requisitos

- Python 3.8+
- Linux ou Windows

---

## Instalação e Execução (Linux)

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Rodar o sistema
python app.py
```

Acesse: **http://localhost:5000**

---

## Login Padrão

| Campo | Valor        |
|-------|--------------|
| CPF   | 00000000000  |
| Senha | admin123     |

---

## Módulos

| Módulo       | Descrição |
|--------------|-----------|
| Usuários     | Cadastro, edição, ativação/desativação de usuários com perfis: Admin, Técnico, Usuário |
| Máquinas     | Patrimônio com tombo, histórico de setor, situação |
| Peças        | Cadastro de peças (nome, categoria, observação) |
| Estoque      | Local e quantidade de cada peça, com entrada/saída e histórico de movimentações |
| Chamados     | Abertura, atribuição, encerramento com solução |
| Relatórios   | Abertos, concluídos, por técnico, por período |

---

## Perfis de Acesso

| Perfil    | Permissões |
|-----------|-----------|
| Admin     | Acesso total, gerencia usuários |
| Técnico   | Assume e encerra chamados, edita máquinas, cadastra peças e gerencia estoque |
| Usuário   | Abre chamados, consulta |

---

## Estrutura de Pastas

```
sistema_ti/
├── app.py              # Backend Flask principal
├── database.db         # Banco SQLite (criado automaticamente)
├── requirements.txt
├── README.md
├── templates/          # HTML (Jinja2)
└── static/
    ├── css/style.css
    └── js/main.js
```

---

## Banco de Dados

O banco `database.db` é criado automaticamente na primeira execução.
O usuário administrador padrão também é criado automaticamente.

---

## Observações

- Senhas armazenadas com hash seguro (Werkzeug)
- Sessão com controle de perfil
- Banco SQLite local, sem necessidade de servidor externo
