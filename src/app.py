from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

def agora():
    return datetime.now()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'oficina-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///oficina.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─── MODELOS ───────────────────────────────────────────────────────────────────

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    perfil = db.Column(db.String(20), nullable=False)
    ativo = db.Column(db.Boolean, default=True)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    criado_em = db.Column(db.DateTime, default=agora)
    veiculos = db.relationship('Veiculo', backref='cliente', lazy=True)

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), unique=True, nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    cor = db.Column(db.String(30))
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    ordens = db.relationship('OrdemServico', backref='veiculo', lazy=True)

class OrdemServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Em aberto')
    valor_total = db.Column(db.Float, default=0.0)
    forma_pagamento = db.Column(db.String(20))
    status_pagamento = db.Column(db.String(20), default='Pendente')
    data_abertura = db.Column(db.DateTime, default=agora)
    data_conclusao = db.Column(db.DateTime)
    data_pagamento = db.Column(db.DateTime)
    motivo_cancelamento = db.Column(db.Text)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    itens = db.relationship('ItemOS', backref='ordem', lazy=True, cascade='all, delete-orphan')

class ItemOS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    quantidade = db.Column(db.Float, nullable=False, default=1)
    valor_unitario = db.Column(db.Float, nullable=False)
    ordem_id = db.Column(db.Integer, db.ForeignKey('ordem_servico.id'), nullable=False)

    @property
    def subtotal(self):
        return self.quantidade * self.valor_unitario

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def perfil_required(*perfis):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('perfil') not in perfis:
                flash('Acesso não autorizado.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

def gerar_numero_os():
    ultima = OrdemServico.query.order_by(OrdemServico.id.desc()).first()
    numero = (ultima.id + 1) if ultima else 1
    return f"OS{numero:04d}"

# ─── ROTAS: AUTH ───────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        usuario = Usuario.query.filter_by(email=email, ativo=True).first()
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            session['nome'] = usuario.nome
            session['perfil'] = usuario.perfil
            return redirect(url_for('dashboard'))
        flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── ROTAS: DASHBOARD ──────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    total_clientes = Cliente.query.count()
    total_veiculos = Veiculo.query.count()
    os_abertas = OrdemServico.query.filter_by(status='Em aberto').count()
    os_andamento = OrdemServico.query.filter_by(status='Em andamento').count()
    os_pendentes = OrdemServico.query.filter_by(status_pagamento='Pendente').filter(OrdemServico.status == 'Concluído').count()
    return render_template('dashboard.html',
        total_clientes=total_clientes,
        total_veiculos=total_veiculos,
        os_abertas=os_abertas,
        os_andamento=os_andamento,
        os_pendentes=os_pendentes)

# ─── ROTAS: CLIENTES ───────────────────────────────────────────────────────────

@app.route('/clientes')
@login_required
def clientes():
    busca = request.args.get('busca', '')
    if busca:
        lista = Cliente.query.filter(
            (Cliente.nome.ilike(f'%{busca}%')) | (Cliente.cpf.ilike(f'%{busca}%'))
        ).all()
    else:
        lista = Cliente.query.order_by(Cliente.nome).all()
    return render_template('clientes.html', clientes=lista, busca=busca)

@app.route('/clientes/novo', methods=['GET', 'POST'])
@login_required
def novo_cliente():
    if request.method == 'POST':
        cpf = request.form.get('cpf')
        if Cliente.query.filter_by(cpf=cpf).first():
            flash('CPF já cadastrado.', 'danger')
            return render_template('cliente_form.html', cliente=None)
        c = Cliente(
            nome=request.form.get('nome'),
            cpf=cpf,
            telefone=request.form.get('telefone'),
            email=request.form.get('email')
        )
        db.session.add(c)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    return render_template('cliente_form.html', cliente=None)

@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    c = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cpf = request.form.get('cpf')
        existente = Cliente.query.filter_by(cpf=cpf).first()
        if existente and existente.id != id:
            flash('CPF já cadastrado para outro cliente.', 'danger')
            return render_template('cliente_form.html', cliente=c)
        c.nome = request.form.get('nome')
        c.cpf = cpf
        c.telefone = request.form.get('telefone')
        c.email = request.form.get('email')
        db.session.commit()
        flash('Cliente atualizado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    return render_template('cliente_form.html', cliente=c)

@app.route('/clientes/<int:id>')
@login_required
def ver_cliente(id):
    c = Cliente.query.get_or_404(id)
    return render_template('cliente_ver.html', cliente=c)

# ─── ROTAS: VEÍCULOS ───────────────────────────────────────────────────────────

@app.route('/veiculos/novo/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def novo_veiculo(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.method == 'POST':
        placa = request.form.get('placa').upper()
        if Veiculo.query.filter_by(placa=placa).first():
            flash('Placa já cadastrada.', 'danger')
            return render_template('veiculo_form.html', cliente=cliente, veiculo=None)
        v = Veiculo(
            placa=placa,
            marca=request.form.get('marca'),
            modelo=request.form.get('modelo'),
            ano=request.form.get('ano'),
            cor=request.form.get('cor'),
            cliente_id=cliente_id
        )
        db.session.add(v)
        db.session.commit()
        flash('Veículo cadastrado com sucesso!', 'success')
        return redirect(url_for('ver_cliente', id=cliente_id))
    return render_template('veiculo_form.html', cliente=cliente, veiculo=None)

@app.route('/veiculos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_veiculo(id):
    v = Veiculo.query.get_or_404(id)
    if request.method == 'POST':
        placa = request.form.get('placa').upper()
        existente = Veiculo.query.filter_by(placa=placa).first()
        if existente and existente.id != id:
            flash('Placa já cadastrada para outro veículo.', 'danger')
            return render_template('veiculo_form.html', cliente=v.cliente, veiculo=v)
        v.placa = placa
        v.marca = request.form.get('marca')
        v.modelo = request.form.get('modelo')
        v.ano = request.form.get('ano')
        v.cor = request.form.get('cor')
        db.session.commit()
        flash('Veículo atualizado com sucesso!', 'success')
        return redirect(url_for('ver_cliente', id=v.cliente_id))
    return render_template('veiculo_form.html', cliente=v.cliente, veiculo=v)

# ─── ROTAS: ORDENS DE SERVIÇO ──────────────────────────────────────────────────

@app.route('/ordens')
@login_required
def ordens():
    status = request.args.get('status', '')
    if status:
        lista = OrdemServico.query.filter_by(status=status).order_by(OrdemServico.data_abertura.desc()).all()
    else:
        lista = OrdemServico.query.order_by(OrdemServico.data_abertura.desc()).all()
    return render_template('ordens.html', ordens=lista, status_filtro=status)

@app.route('/ordens/nova', methods=['GET', 'POST'])
@login_required
def nova_ordem():
    clientes = Cliente.query.order_by(Cliente.nome).all()
    if request.method == 'POST':
        veiculo_id = request.form.get('veiculo_id')
        os = OrdemServico(
            numero=gerar_numero_os(),
            descricao=request.form.get('descricao'),
            veiculo_id=veiculo_id
        )
        db.session.add(os)
        db.session.commit()
        flash(f'Ordem {os.numero} aberta com sucesso!', 'success')
        return redirect(url_for('ver_ordem', id=os.id))
    return render_template('ordem_form.html', clientes=clientes)

@app.route('/ordens/<int:id>')
@login_required
def ver_ordem(id):
    os = OrdemServico.query.get_or_404(id)
    return render_template('ordem_ver.html', os=os)

@app.route('/ordens/<int:id>/status', methods=['POST'])
@login_required
def atualizar_status(id):
    os = OrdemServico.query.get_or_404(id)
    novo_status = request.form.get('status')
    ordem_status = ['Em aberto', 'Em andamento', 'Concluído']
    if ordem_status.index(novo_status) > ordem_status.index(os.status):
        os.status = novo_status
        if novo_status == 'Concluído':
            os.data_conclusao = agora()
        db.session.commit()
        flash('Status atualizado!', 'success')
    else:
        flash('Não é possível voltar ao status anterior.', 'danger')
    return redirect(url_for('ver_ordem', id=id))

@app.route('/ordens/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar_ordem(id):
    os = OrdemServico.query.get_or_404(id)
    if os.status != 'Em aberto':
        flash('Só é possível cancelar ordens em aberto.', 'danger')
        return redirect(url_for('ver_ordem', id=id))
    os.status = 'Cancelado'
    os.motivo_cancelamento = request.form.get('motivo')
    db.session.commit()
    flash('Ordem cancelada.', 'warning')
    return redirect(url_for('ordens'))

@app.route('/ordens/<int:id>/item', methods=['POST'])
@login_required
def adicionar_item(id):
    os = OrdemServico.query.get_or_404(id)
    item = ItemOS(
        descricao=request.form.get('descricao'),
        quantidade=float(request.form.get('quantidade', 1)),
        valor_unitario=float(request.form.get('valor_unitario', 0)),
        ordem_id=id
    )
    db.session.add(item)
    db.session.flush()
    os.valor_total = sum(i.subtotal for i in os.itens)
    db.session.commit()
    flash('Item adicionado!', 'success')
    return redirect(url_for('ver_ordem', id=id))

@app.route('/ordens/<int:id>/item/<int:item_id>/remover', methods=['POST'])
@login_required
def remover_item(id, item_id):
    item = ItemOS.query.get_or_404(item_id)
    os = OrdemServico.query.get_or_404(id)
    db.session.delete(item)
    db.session.flush()
    os.valor_total = sum(i.subtotal for i in os.itens if i.id != item_id)
    db.session.commit()
    flash('Item removido.', 'success')
    return redirect(url_for('ver_ordem', id=id))

# ─── ROTAS: PAGAMENTO ──────────────────────────────────────────────────────────

@app.route('/ordens/<int:id>/pagar', methods=['POST'])
@login_required
def registrar_pagamento(id):
    os = OrdemServico.query.get_or_404(id)
    os.forma_pagamento = request.form.get('forma_pagamento')
    os.status_pagamento = 'Pago'
    os.data_pagamento = agora()
    db.session.commit()
    flash('Pagamento registrado com sucesso!', 'success')
    return redirect(url_for('ver_ordem', id=id))

@app.route('/relatorios')
@login_required
@perfil_required('gestor')
def relatorios():
    periodo = request.args.get('periodo', 'mes')
    from datetime import timedelta
    hoje = agora()
    if periodo == 'dia':
        inicio = hoje.replace(hour=0, minute=0, second=0)
    elif periodo == 'semana':
        inicio = hoje - timedelta(days=7)
    else:
        inicio = hoje.replace(day=1, hour=0, minute=0, second=0)

    os_periodo = OrdemServico.query.filter(OrdemServico.data_abertura >= inicio).all()
    os_pagas = [o for o in os_periodo if o.status_pagamento == 'Pago']
    total_arrecadado = sum(o.valor_total for o in os_pagas)
    por_status = {
        'Em aberto': len([o for o in os_periodo if o.status == 'Em aberto']),
        'Em andamento': len([o for o in os_periodo if o.status == 'Em andamento']),
        'Concluído': len([o for o in os_periodo if o.status == 'Concluído']),
        'Cancelado': len([o for o in os_periodo if o.status == 'Cancelado']),
    }
    por_pagamento = {
        'Dinheiro': sum(o.valor_total for o in os_pagas if o.forma_pagamento == 'Dinheiro'),
        'Cartão de débito': sum(o.valor_total for o in os_pagas if o.forma_pagamento == 'Cartão de débito'),
        'Cartão de crédito': sum(o.valor_total for o in os_pagas if o.forma_pagamento == 'Cartão de crédito'),
        'PIX': sum(o.valor_total for o in os_pagas if o.forma_pagamento == 'PIX'),
    }
    return render_template('relatorios.html',
        periodo=periodo,
        os_periodo=os_periodo,
        os_pagas=os_pagas,
        total_arrecadado=total_arrecadado,
        por_status=por_status,
        por_pagamento=por_pagamento)

@app.route('/pagamentos/pendentes')
@login_required
def pagamentos_pendentes():
    lista = OrdemServico.query.filter_by(status='Concluído', status_pagamento='Pendente').order_by(OrdemServico.data_conclusao).all()
    return render_template('pagamentos_pendentes.html', ordens=lista)

# ─── ROTAS: USUÁRIOS ───────────────────────────────────────────────────────────

@app.route('/usuarios')
@login_required
@perfil_required('gestor')
def usuarios():
    lista = Usuario.query.all()
    return render_template('usuarios.html', usuarios=lista)

@app.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
@perfil_required('gestor')
def novo_usuario():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form.get('email')).first():
            flash('E-mail já cadastrado.', 'danger')
            return render_template('usuario_form.html', usuario=None)
        u = Usuario(
            nome=request.form.get('nome'),
            email=request.form.get('email'),
            senha=generate_password_hash(request.form.get('senha')),
            perfil=request.form.get('perfil')
        )
        db.session.add(u)
        db.session.commit()
        flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('usuarios'))
    return render_template('usuario_form.html', usuario=None)

@app.route('/usuarios/<int:id>/senha', methods=['POST'])
@login_required
@perfil_required('gestor')
def redefinir_senha(id):
    u = Usuario.query.get_or_404(id)
    nova = request.form.get('nova_senha')
    if len(nova) < 6:
        flash('A senha deve ter no mínimo 6 caracteres.', 'danger')
        return redirect(url_for('usuarios'))
    u.senha = generate_password_hash(nova)
    db.session.commit()
    flash(f'Senha de {u.nome} redefinida com sucesso!', 'success')
    return redirect(url_for('usuarios'))

# ─── ROTAS: API ────────────────────────────────────────────────────────────────

@app.route('/api/veiculos/<int:cliente_id>')
@login_required
def api_veiculos(cliente_id):
    veiculos = Veiculo.query.filter_by(cliente_id=cliente_id).all()
    return {'veiculos': [{'id': v.id, 'texto': f'{v.placa} - {v.marca} {v.modelo}'} for v in veiculos]}

# ─── INIT ──────────────────────────────────────────────────────────────────────

def criar_banco():
    with app.app_context():
        db.create_all()
        if not Usuario.query.filter_by(email='admin@oficina.com').first():
            admin = Usuario(
                nome='Administrador',
                email='admin@oficina.com',
                senha=generate_password_hash('admin123'),
                perfil='gestor'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuário admin criado: admin@oficina.com / admin123")

if __name__ == '__main__':
    criar_banco()
    app.run(debug=True)
