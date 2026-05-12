"""
database.py — Camada de Modelo (Model) do padrão MVC.

Responsabilidade exclusiva: encapsular toda e qualquer interação com o banco
de dados SQLite. Nenhuma rota ou lógica de apresentação deve residir aqui.

Justificativa acadêmica (Clean Code / Separação de Responsabilidades):
  - Cada função executa UMA operação de negócio bem definida.
  - O app.py (Controller) chama estas funções sem conhecer os detalhes do SQL.
  - Facilita testes unitários isolados e futuras migrações de banco de dados.
"""

import sqlite3
import os

# ─── CONFIGURAÇÃO CENTRAL DO BANCO ───────────────────────────────────────────
# O caminho do banco é resolvido em relação ao diretório deste arquivo,
# garantindo que a aplicação funcione independente do diretório de trabalho.
DB_PATH = os.path.join(os.path.dirname(__file__), 'livros.db')

# ─── DIVISOR DE XP (REGRA DE NEGÓCIO CENTRAL) ────────────────────────────────
# Cada 300 páginas lidas equivalem a 1 nível. Centralizar esta constante aqui
# garante que qualquer alteração na regra de negócio seja feita em um único lugar.
DIVISOR_XP = 300


def get_conexao():
    """
    Retorna uma conexão com o banco de dados SQLite.

    Usar row_factory = sqlite3.Row permite acessar colunas pelo nome
    (ex: row['titulo']) em vez de índice numérico (ex: row[1]),
    tornando o código do template muito mais legível e menos propenso a erros
    quando a ordem das colunas mudar.
    """
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    return conexao


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: USUÁRIOS
# ══════════════════════════════════════════════════════════════════════════════

def buscar_usuario_por_credenciais(email: str, senha: str):
    """
    Verifica as credenciais de login e retorna os dados do usuário se válidas.

    Retorna um objeto sqlite3.Row com {id, nome, tipo} ou None se não encontrado.
    Nota de segurança: em produção real, 'senha' deveria ser um hash (bcrypt/argon2).
    Para o escopo do PI, utilizamos texto plano para simplificar a demonstração.
    """
    with get_conexao() as conn:
        return conn.execute(
            "SELECT id, nome, tipo FROM usuarios WHERE email = ? AND senha = ?",
            (email, senha)
        ).fetchone()


def salvar_usuario(nome: str, email: str, senha: str, tipo: str):
    """
    Insere um novo usuário no banco de dados.

    Levanta sqlite3.IntegrityError se o e-mail já estiver cadastrado,
    pois a coluna 'email' possui restrição UNIQUE.
    O tipo ('admin' ou 'usuario') é determinado pelo Controller antes da chamada.
    """
    with get_conexao() as conn:
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)",
            (nome, email, senha, tipo)
        )


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ESTANTE PESSOAL (Livros do usuário)
# ══════════════════════════════════════════════════════════════════════════════

def buscar_livros_do_usuario(usuario_id: int):
    """
    Retorna todos os livros cadastrados por um usuário específico,
    incluindo o status (pendente/aprovado/rejeitado) para exibição das etiquetas.
    """
    with get_conexao() as conn:
        return conn.execute(
            "SELECT id, titulo, paginas, capa, status FROM livros WHERE usuario_id = ?",
            (usuario_id,)
        ).fetchall()


def calcular_xp_usuario(usuario_id: int) -> int:
    """
    Calcula o XP total de um usuário somando as páginas APENAS dos livros aprovados.

    Justificativa da regra de negócio: somente o Admin pode validar que um livro
    foi realmente lido. Livros 'pendentes' ou 'rejeitados' não contam para o XP,
    evitando fraudes no ranking.
    """
    with get_conexao() as conn:
        resultado = conn.execute(
            "SELECT SUM(paginas) FROM livros WHERE usuario_id = ? AND status = 'aprovado'",
            (usuario_id,)
        ).fetchone()[0]
    return resultado if resultado else 0


def salvar_livro(titulo: str, paginas: int, capa: str, usuario_id: int):
    """
    Insere um novo livro na estante do usuário com status 'pendente'.

    O status 'pendente' é o valor padrão porque todo novo registro de leitura
    precisa ser validado pelo bibliotecário (Admin) antes de gerar XP.
    Isso garante a integridade do sistema de gamificação.
    """
    with get_conexao() as conn:
        conn.execute(
            "INSERT INTO livros (titulo, paginas, capa, status, usuario_id) VALUES (?, ?, ?, 'pendente', ?)",
            (titulo, paginas, capa, usuario_id)
        )


def deletar_livro_do_usuario(livro_id: int, usuario_id: int):
    """
    Remove um livro da estante, garantindo que o usuário só possa deletar
    seus próprios livros (cláusula AND usuario_id = ?).

    Esta verificação dupla (id + usuario_id) é uma salvaguarda de segurança
    contra remoções maliciosas via manipulação de URL.
    """
    with get_conexao() as conn:
        conn.execute(
            "DELETE FROM livros WHERE id = ? AND usuario_id = ?",
            (livro_id, usuario_id)
        )


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: RESENHAS
# ══════════════════════════════════════════════════════════════════════════════

def buscar_todas_resenhas():
    """
    Retorna todas as resenhas em ordem cronológica decrescente (mais recentes primeiro),
    fazendo JOIN com usuários e livros para obter os dados necessários para o feed.

    A consulta usa aliases explícitos para tornar o acesso por nome mais claro.
    """
    with get_conexao() as conn:
        return conn.execute("""
            SELECT
                u.nome          AS nome_usuario,
                l.titulo        AS titulo_livro,
                r.texto         AS texto,
                r.nota          AS nota,
                r.data_postagem AS data_postagem,
                l.capa          AS capa,
                r.id            AS id,
                r.usuario_id    AS usuario_id
            FROM resenhas r
            JOIN usuarios u ON r.usuario_id = u.id
            JOIN livros l ON r.livro_id = l.id
            ORDER BY r.data_postagem DESC
        """).fetchall()


def salvar_resenha(usuario_id: int, livro_id: int, texto: str, nota: int):
    """
    Insere uma nova resenha no banco de dados.
    A data de postagem é gerada automaticamente pelo SQLite (DEFAULT CURRENT_TIMESTAMP).
    """
    with get_conexao() as conn:
        conn.execute(
            "INSERT INTO resenhas (usuario_id, livro_id, texto, nota) VALUES (?, ?, ?, ?)",
            (usuario_id, livro_id, texto, nota)
        )


def deletar_resenha_do_usuario(resenha_id: int, usuario_id: int):
    """
    Remove uma resenha, garantindo que apenas o autor possa excluí-la.
    Mesma lógica de segurança aplicada em deletar_livro_do_usuario.
    """
    with get_conexao() as conn:
        conn.execute(
            "DELETE FROM resenhas WHERE id = ? AND usuario_id = ?",
            (resenha_id, usuario_id)
        )


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: RANKING
# ══════════════════════════════════════════════════════════════════════════════

def buscar_ranking():
    """
    Retorna o ranking geral de leitores, ordenado por XP (total de páginas aprovadas).

    Utiliza LEFT JOIN para incluir usuários que ainda não têm livros aprovados,
    garantindo que todos os cadastrados apareçam no ranking (com XP = 0).
    COALESCE converte NULL em 0 para leitores sem livros aprovados.
    """
    with get_conexao() as conn:
        return conn.execute("""
            SELECT
                u.nome                      AS nome,
                COALESCE(SUM(l.paginas), 0) AS xp,
                COUNT(l.id)                 AS total_livros
            FROM usuarios u
            LEFT JOIN livros l ON u.id = l.usuario_id AND l.status = 'aprovado'
            GROUP BY u.id, u.nome
            ORDER BY xp DESC
        """).fetchall()


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ACERVO FÍSICO DA BIBLIOTECA (Gestão do Admin)
# ══════════════════════════════════════════════════════════════════════════════

def buscar_acervo_completo():
    """Retorna todos os livros do acervo físico ordenados alfabeticamente."""
    with get_conexao() as conn:
        return conn.execute(
            "SELECT id, titulo, autor, paginas, patrimonio, capa, status FROM acervo ORDER BY titulo ASC"
        ).fetchall()


def buscar_estatisticas_acervo() -> dict:
    """
    Retorna um dicionário com as contagens do acervo para o painel admin.

    Agrupa as três consultas em uma única função para que o Controller
    precise fazer apenas uma chamada para obter todos os dados do dashboard.
    """
    with get_conexao() as conn:
        total = conn.execute("SELECT COUNT(id) FROM acervo").fetchone()[0]
        disponiveis = conn.execute("SELECT COUNT(id) FROM acervo WHERE status = 'Disponível'").fetchone()[0]
        emprestados = conn.execute("SELECT COUNT(id) FROM acervo WHERE status = 'Emprestado'").fetchone()[0]
    return {"total": total, "disponiveis": disponiveis, "emprestados": emprestados}


def adicionar_livro_acervo(titulo: str, autor: str, paginas: int, patrimonio: str, capa: str):
    """
    Insere um novo título no acervo físico da biblioteca.
    O status padrão é 'Disponível', pois ao ser cadastrado o livro está na estante.
    """
    with get_conexao() as conn:
        conn.execute(
            "INSERT INTO acervo (titulo, autor, paginas, patrimonio, capa, status) VALUES (?, ?, ?, ?, ?, 'Disponível')",
            (titulo, autor, paginas, patrimonio, capa)
        )


def atualizar_status_acervo(livro_id: int, novo_status: str):
    """
    Atualiza o status de disponibilidade de um livro do acervo.
    Valores válidos: 'Disponível', 'Emprestado', 'Manutenção'.
    """
    with get_conexao() as conn:
        conn.execute(
            "UPDATE acervo SET status = ? WHERE id = ?",
            (novo_status, livro_id)
        )


def remover_livro_acervo(livro_id: int):
    """Remove permanentemente um livro do acervo físico da biblioteca."""
    with get_conexao() as conn:
        conn.execute("DELETE FROM acervo WHERE id = ?", (livro_id,))


def buscar_acervo_publico():
    """
    Retorna dois grupos de livros para a página pública do acervo:
      - disponíveis: obras que estão na estante e podem ser retiradas.
      - indisponiveis: obras emprestadas ou em manutenção.

    Separar em duas listas no Model evita lógica condicional complexa no template.
    """
    with get_conexao() as conn:
        disponiveis = conn.execute(
            "SELECT id, titulo, autor, paginas, patrimonio, capa, status FROM acervo WHERE status = 'Disponível'"
        ).fetchall()
        indisponiveis = conn.execute(
            "SELECT id, titulo, autor, paginas, patrimonio, capa, status FROM acervo WHERE status != 'Disponível'"
        ).fetchall()
    return disponiveis, indisponiveis


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: PAINEL ADMIN — APROVAÇÃO DE LEITURAS
# ══════════════════════════════════════════════════════════════════════════════

def buscar_livros_pendentes():
    """
    Retorna todos os livros aguardando validação pelo Admin.
    O JOIN com usuários é necessário para identificar a quem pertence cada livro.
    """
    with get_conexao() as conn:
        return conn.execute("""
            SELECT l.id, l.titulo, l.paginas, l.capa, u.nome, u.email
            FROM livros l
            JOIN usuarios u ON l.usuario_id = u.id
            WHERE l.status = 'pendente'
        """).fetchall()


def aprovar_livro(livro_id: int):
    """
    Aprova um livro pendente, liberando seu XP para o usuário.
    Esta é a ação central da curadoria do bibliotecário.
    """
    with get_conexao() as conn:
        conn.execute(
            "UPDATE livros SET status = 'aprovado' WHERE id = ?",
            (livro_id,)
        )


def rejeitar_livro(livro_id: int):
    """
    Rejeita um livro pendente. O XP correspondente não é computado no ranking.
    O livro permanece na estante do usuário com a etiqueta 'Rejeitado'.
    """
    with get_conexao() as conn:
        conn.execute(
            "UPDATE livros SET status = 'rejeitado' WHERE id = ?",
            (livro_id,)
        )


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: DADOS GLOBAIS DE SESSÃO
# ══════════════════════════════════════════════════════════════════════════════

def buscar_dados_globais_usuario(usuario_id: int) -> dict:
    """
    Agrega os dados de XP e nível para injeção no contexto global do Jinja2.

    Esta função alimenta o context_processor do Flask, que disponibiliza
    'global_xp', 'global_livros' e 'global_nivel' em TODOS os templates,
    sem que cada rota precise buscá-los individualmente.
    """
    with get_conexao() as conn:
        resultado = conn.execute(
            "SELECT SUM(paginas), COUNT(id) FROM livros WHERE usuario_id = ? AND status = 'aprovado'",
            (usuario_id,)
        ).fetchone()

    xp = resultado[0] if resultado[0] else 0
    total_livros = resultado[1] if resultado[1] else 0
    nivel = (xp // DIVISOR_XP) + 1

    return {
        'global_xp': xp,
        'global_livros': total_livros,
        'global_nivel': nivel,
    }
