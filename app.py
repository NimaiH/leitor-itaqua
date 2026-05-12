"""
app.py — Camada de Controle (Controller) do padrão MVC.

Responsabilidade exclusiva: receber requisições HTTP, orquestrar as chamadas
às funções do Model (database.py) e decidir qual View (template) renderizar.

Este arquivo NÃO deve conter consultas SQL diretas. Toda a lógica de dados
está encapsulada no database.py, seguindo o princípio da Separação de
Responsabilidades (SoC — Separation of Concerns).

Configuração de ambiente:
  As variáveis sensíveis (SECRET_KEY) são lidas de um arquivo .env via
  python-dotenv, evitando que segredos sejam versionados no Git.
"""

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

import database as db

# ─── CONFIGURAÇÃO DA APLICAÇÃO ────────────────────────────────────────────────
# Carrega as variáveis do arquivo .env para o ambiente antes de qualquer uso.
load_dotenv()

app = Flask(__name__)

# A SECRET_KEY é lida do ambiente (.env). Em produção, deve ser uma string
# longa e aleatória. Nunca deve ser commitada diretamente no código-fonte.
app.secret_key = os.environ.get('SECRET_KEY', 'chave-de-desenvolvimento-insegura')

# Diretório para armazenamento de imagens enviadas pelos usuários (capas de livros).
os.makedirs('static/uploads', exist_ok=True)
app.config['UPLOAD_FOLDER'] = 'static/uploads'


# ─── HELPERS INTERNOS ─────────────────────────────────────────────────────────

def _processar_upload_capa(request_files, campo: str, fallback_url: str) -> str:
    """
    Verifica se um arquivo de imagem foi enviado no formulário e o salva.

    Retorna o caminho público da imagem salva ou a URL de fallback caso
    nenhum arquivo tenha sido enviado. Centralizar esta lógica evita
    duplicação de código entre as rotas de livros e de acervo.
    """
    if campo in request_files:
        imagem = request_files[campo]
        if imagem.filename != '':
            nome_arquivo = secure_filename(imagem.filename)
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
            imagem.save(caminho)
            # Normaliza separadores de path para garantir URLs válidas em Windows e Linux
            return '/static/uploads/' + nome_arquivo.replace('\\', '/')
    return fallback_url


def _requer_login():
    """Redireciona para login se o usuário não estiver autenticado."""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    return None


def _requer_admin():
    """Redireciona para a estante se o usuário não for administrador."""
    if session.get('usuario_tipo') != 'admin':
        return redirect(url_for('estante'))
    return None


# ─── INJEÇÃO DE DADOS GLOBAIS ─────────────────────────────────────────────────
@app.context_processor
def injetar_dados_usuario():
    """
    Injeta variáveis de XP e nível em TODOS os templates Jinja2.

    O context_processor é executado antes de cada renderização de template.
    Usar o Model (database.py) aqui garante que a navbar sempre exiba dados
    atualizados sem que cada rota precise buscá-los individualmente.
    """
    if session.get('usuario_id'):
        dados = db.buscar_dados_globais_usuario(session['usuario_id'])
        dados['is_admin'] = session.get('usuario_tipo') == 'admin'
        return dados
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# ROTAS PÚBLICAS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    """Página inicial (landing page). Acessível sem autenticação."""
    return render_template('index.html')


@app.route('/sobre')
def sobre():
    """Página institucional sobre a Biblioteca Municipal de Itaquaquecetuba."""
    return render_template('sobre.html')


@app.route('/acervo_publico')
def acervo_publico():
    """
    Exibe o catálogo de livros do acervo físico da biblioteca.
    Acessível a visitantes não autenticados para promover a biblioteca.
    """
    disponiveis, indisponiveis = db.buscar_acervo_publico()
    return render_template('acervo_publico.html',
                           livros_disponiveis=disponiveis,
                           livros_indisponiveis=indisponiveis)


# ══════════════════════════════════════════════════════════════════════════════
# ROTAS DE AUTENTICAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    GET:  Exibe o formulário de login.
    POST: Valida credenciais e inicia a sessão do usuário.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        usuario = db.buscar_usuario_por_credenciais(email, senha)

        if usuario:
            # Armazena apenas os dados necessários na sessão (id, nome, tipo).
            # Nunca armazenar a senha na sessão.
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            session['usuario_tipo'] = usuario['tipo']
            return redirect(url_for('estante'))

        return render_template('login.html', erro="E-mail ou senha incorretos.")

    return render_template('login.html')


@app.route('/cadastro')
def cadastro():
    """Exibe o formulário de criação de conta."""
    return render_template('cadastro.html')


@app.route('/salvar_usuario', methods=['POST'])
def salvar_usuario():
    """
    Processa o formulário de cadastro e cria um novo usuário.

    Regra de negócio: o e-mail 'admin@itaqua.com' recebe tipo 'admin'
    automaticamente. Esta abordagem simplificada é adequada para o escopo
    do PI; em produção, usaríamos um fluxo de promoção de perfil dedicado.
    """
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha = request.form.get('senha')
    tipo = 'admin' if email == 'admin@itaqua.com' else 'usuario'

    try:
        db.salvar_usuario(nome, email, senha, tipo)
    except sqlite3.IntegrityError:
        # sqlite3.IntegrityError é lançado quando o e-mail já existe (UNIQUE constraint)
        return render_template('cadastro.html', erro="Este e-mail já está cadastrado.")

    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    """Encerra a sessão do usuário e redireciona para a página sobre."""
    session.clear()
    return redirect(url_for('sobre'))


# ══════════════════════════════════════════════════════════════════════════════
# ROTAS AUTENTICADAS — ESTANTE PESSOAL
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/estante')
def estante():
    """
    Exibe a estante pessoal do usuário com seu painel de XP e nível.
    Requer autenticação.
    """
    guard = _requer_login()
    if guard:
        return guard

    livros = db.buscar_livros_do_usuario(session['usuario_id'])
    xp = db.calcular_xp_usuario(session['usuario_id'])
    return render_template('estante.html', livros=livros, xp=xp)


@app.route('/cadastrar_livros')
def cadastrar_livros():
    """Exibe o formulário para registrar um novo livro na estante. Requer autenticação."""
    guard = _requer_login()
    if guard:
        return guard
    return render_template('cadastrar_livros.html')


@app.route('/salvar_livro', methods=['POST'])
def salvar_livro():
    """
    Processa o envio de um novo livro.
    O livro entra com status 'pendente' e aguarda aprovação do Admin.
    Requer autenticação.
    """
    guard = _requer_login()
    if guard:
        return guard

    titulo = request.form.get('titulo')
    paginas = request.form.get('paginas')
    capa = _processar_upload_capa(
        request.files, 'capa_imagem',
        fallback_url='https://via.placeholder.com/150x200?text=Sem+Capa'
    )

    db.salvar_livro(titulo, paginas, capa, session['usuario_id'])
    return redirect(url_for('estante'))


@app.route('/deletar_livro/<int:livro_id>')
def deletar_livro(livro_id: int):
    """Remove um livro da estante do usuário autenticado. Requer autenticação."""
    guard = _requer_login()
    if guard:
        return guard

    db.deletar_livro_do_usuario(livro_id, session['usuario_id'])
    return redirect(url_for('estante'))


# ══════════════════════════════════════════════════════════════════════════════
# ROTAS AUTENTICADAS — COMUNIDADE
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/ranking')
def ranking():
    """
    Exibe o ranking geral de leitores por XP acumulado.
    Requer autenticação para fomentar o cadastro na plataforma.
    """
    guard = _requer_login()
    if guard:
        return guard

    dados = db.buscar_ranking()
    # O DIVISOR_XP é passado ao template para calcular o nível de cada leitor
    return render_template('ranking.html', ranking=dados, divisor=db.DIVISOR_XP)


@app.route('/resenhas')
def resenhas():
    """
    Exibe o mural de resenhas da comunidade e o formulário para nova resenha.
    Requer autenticação.
    """
    guard = _requer_login()
    if guard:
        return guard

    todas_resenhas = db.buscar_todas_resenhas()
    # A lista de livros do usuário é necessária para o modal de seleção de livro
    meus_livros = db.buscar_livros_do_usuario(session['usuario_id'])
    return render_template('resenhas.html', resenhas=todas_resenhas, meus_livros=meus_livros)


@app.route('/salvar_resenha', methods=['POST'])
def salvar_resenha():
    """Processa o envio de uma nova resenha. Requer autenticação."""
    guard = _requer_login()
    if guard:
        return guard

    db.salvar_resenha(
        usuario_id=session['usuario_id'],
        livro_id=request.form.get('livro_id'),
        texto=request.form.get('texto'),
        nota=request.form.get('nota')
    )
    return redirect(url_for('resenhas'))


@app.route('/deletar_resenha/<int:resenha_id>')
def deletar_resenha(resenha_id: int):
    """Remove uma resenha do usuário autenticado. Requer autenticação."""
    guard = _requer_login()
    if guard:
        return guard

    db.deletar_resenha_do_usuario(resenha_id, session['usuario_id'])
    return redirect(url_for('resenhas'))


# ══════════════════════════════════════════════════════════════════════════════
# ROTAS ADMINISTRATIVAS — ACESSO RESTRITO
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/pendentes')
def admin_pendentes():
    """
    Painel de aprovação de leituras.
    Exibe todos os livros com status 'pendente' para curadoria do Admin.
    """
    guard = _requer_admin()
    if guard:
        return guard

    pendentes = db.buscar_livros_pendentes()
    return render_template('admin_pendentes.html', pendentes=pendentes)


@app.route('/admin/aprovar/<int:livro_id>')
def aprovar_livro(livro_id: int):
    """Aprova um livro pendente, liberando o XP para o usuário."""
    guard = _requer_admin()
    if guard:
        return guard

    db.aprovar_livro(livro_id)
    return redirect(url_for('admin_pendentes'))


@app.route('/admin/rejeitar/<int:livro_id>')
def rejeitar_livro(livro_id: int):
    """Rejeita um livro pendente. O XP não é concedido ao usuário."""
    guard = _requer_admin()
    if guard:
        return guard

    db.rejeitar_livro(livro_id)
    return redirect(url_for('admin_pendentes'))


@app.route('/admin/acervo')
def admin_acervo():
    """
    Painel de gestão do acervo físico.
    Exibe o inventário completo com estatísticas de disponibilidade.
    """
    guard = _requer_admin()
    if guard:
        return guard

    acervo = db.buscar_acervo_completo()
    stats = db.buscar_estatisticas_acervo()
    return render_template('admin_acervo.html', acervo=acervo, **stats)


@app.route('/admin/adicionar_acervo', methods=['POST'])
def adicionar_acervo():
    """Processa o cadastro de um novo livro no acervo físico da biblioteca."""
    guard = _requer_admin()
    if guard:
        return guard

    titulo = request.form.get('titulo')
    autor = request.form.get('autor')
    paginas = request.form.get('paginas')
    patrimonio = request.form.get('patrimonio')
    capa = _processar_upload_capa(
        request.files, 'capa_imagem',
        fallback_url='https://via.placeholder.com/40x60?text=Sem+Capa'
    )

    db.adicionar_livro_acervo(titulo, autor, paginas, patrimonio, capa)
    return redirect(url_for('admin_acervo'))


@app.route('/admin/status_acervo/<int:livro_id>/<novo_status>')
def status_acervo(livro_id: int, novo_status: str):
    """Atualiza o status de disponibilidade de um livro do acervo físico."""
    guard = _requer_admin()
    if guard:
        return guard

    db.atualizar_status_acervo(livro_id, novo_status)
    return redirect(url_for('admin_acervo'))


@app.route('/admin/remover_acervo/<int:livro_id>')
def remover_acervo(livro_id: int):
    """Remove permanentemente um livro do acervo físico."""
    guard = _requer_admin()
    if guard:
        return guard

    db.remover_livro_acervo(livro_id)
    return redirect(url_for('admin_acervo'))


# ─── PONTO DE ENTRADA ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    # debug=True nunca deve ser usado em produção.
    # Para produção, use um servidor WSGI como Gunicorn ou uWSGI.
    app.run(debug=True)
