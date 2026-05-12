"""
setup_db.py — Script de inicialização do banco de dados.

Responsabilidade exclusiva: criar as tabelas do banco de dados caso não existam.
Este script deve ser executado UMA ÚNICA VEZ antes de iniciar a aplicação pela
primeira vez, ou sempre que o banco de dados for resetado.

Uso:
    python setup_db.py

Justificativa de separação: manter a criação do schema aqui — e não no app.py —
segue o princípio da Responsabilidade Única (SRP). O app.py inicia o servidor;
este script inicializa a infraestrutura de dados.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'livros.db')


def init_db():
    """Cria todas as tabelas necessárias para o funcionamento da aplicação."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Tabela de Usuários ──────────────────────────────────────────────────
    # 'tipo' define o nível de acesso: 'usuario' (padrão) ou 'admin'.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            nome  TEXT    NOT NULL,
            email TEXT    UNIQUE NOT NULL,
            senha TEXT    NOT NULL,
            tipo  TEXT    DEFAULT 'usuario'
        )
    ''')

    # ── Tabela da Estante Pessoal (Livros dos Usuários) ─────────────────────
    # 'status' controla o fluxo de gamificação: pendente → aprovado | rejeitado.
    # Apenas livros 'aprovados' somam XP ao usuário.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS livros (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo     TEXT    NOT NULL,
            paginas    INTEGER NOT NULL,
            capa       TEXT,
            status     TEXT    DEFAULT 'pendente',
            usuario_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')

    # ── Tabela do Acervo Físico da Biblioteca ───────────────────────────────
    # Gerenciado exclusivamente pelo Admin. Representa o inventário real.
    # 'patrimonio' é o código de tombamento do livro (ex: C0001).
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acervo (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo     TEXT    NOT NULL,
            autor      TEXT    NOT NULL,
            paginas    INTEGER NOT NULL,
            patrimonio TEXT,
            capa       TEXT,
            status     TEXT    DEFAULT 'Disponível'
        )
    ''')

    # ── Tabela de Resenhas ──────────────────────────────────────────────────
    # Alimenta o mural social da aplicação. Cada resenha está vinculada a um
    # usuário E a um livro da estante pessoal (não do acervo físico).
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resenhas (
            id            INTEGER  PRIMARY KEY AUTOINCREMENT,
            usuario_id    INTEGER,
            livro_id      INTEGER,
            texto         TEXT,
            nota          INTEGER,
            data_postagem DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (livro_id)   REFERENCES livros(id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"✅ Banco de dados criado/verificado com sucesso em: {DB_PATH}")


if __name__ == '__main__':
    init_db()
