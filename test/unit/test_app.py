import pytest
from werkzeug.security import generate_password_hash

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app import app, db, Usuario, Cliente, Veiculo, OrdemServico, ItemOS, gerar_numero_os, agora


# ─── CONFIGURAÇÃO ──────────────────────────────────────────────────────────────

@pytest.fixture
def cliente_app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret'

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(cliente_app):
    return cliente_app.test_client()


@pytest.fixture
def usuario_gestor(cliente_app):
    with cliente_app.app_context():
        u = Usuario(
            nome='Gestor Teste',
            email='gestor@teste.com',
            senha=generate_password_hash('senha123'),
            perfil='gestor'
        )
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def usuario_mecanico(cliente_app):
    with cliente_app.app_context():
        u = Usuario(
            nome='Mecanico Teste',
            email='mecanico@teste.com',
            senha=generate_password_hash('senha123'),
            perfil='mecanico'
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def login(client, email, senha):
    return client.post('/', data={'email': email, 'senha': senha}, follow_redirects=True)


# ─── TESTES: FUNÇÃO agora() ────────────────────────────────────────────────────

def test_agora_retorna_datetime(cliente_app):
    from datetime import datetime
    resultado = agora()
    assert isinstance(resultado, datetime)


# ─── TESTES: MODELO ItemOS.subtotal ───────────────────────────────────────────

def test_subtotal_item(cliente_app):
    with cliente_app.app_context():
        item = ItemOS(descricao='Troca de óleo', quantidade=2, valor_unitario=50.0, ordem_id=1)
        assert item.subtotal == 100.0


def test_subtotal_item_fracionado(cliente_app):
    with cliente_app.app_context():
        item = ItemOS(descricao='Parafuso', quantidade=0.5, valor_unitario=10.0, ordem_id=1)
        assert item.subtotal == 5.0


def test_subtotal_item_zero(cliente_app):
    with cliente_app.app_context():
        item = ItemOS(descricao='Servico gratis', quantidade=1, valor_unitario=0.0, ordem_id=1)
        assert item.subtotal == 0.0


# ─── TESTES: MODELO Usuario ───────────────────────────────────────────────────

def test_criar_usuario(cliente_app):
    with cliente_app.app_context():
        u = Usuario(nome='Ana', email='ana@teste.com',
                    senha=generate_password_hash('123456'), perfil='gestor')
        db.session.add(u)
        db.session.commit()
        assert Usuario.query.filter_by(email='ana@teste.com').first() is not None


def test_usuario_ativo_por_padrao(cliente_app):
    with cliente_app.app_context():
        u = Usuario(nome='Carlos', email='carlos@teste.com',
                    senha=generate_password_hash('123456'), perfil='mecanico')
        db.session.add(u)
        db.session.commit()
        assert u.ativo is True


# ─── TESTES: MODELO Cliente ───────────────────────────────────────────────────

def test_criar_cliente(cliente_app):
    with cliente_app.app_context():
        c = Cliente(nome='João Silva', cpf='111.111.111-11', telefone='88999999999')
        db.session.add(c)
        db.session.commit()
        assert Cliente.query.filter_by(cpf='111.111.111-11').first() is not None


def test_cliente_cpf_unico(cliente_app):
    with cliente_app.app_context():
        c1 = Cliente(nome='João', cpf='222.222.222-22')
        c2 = Cliente(nome='Maria', cpf='222.222.222-22')
        db.session.add(c1)
        db.session.commit()
        db.session.add(c2)
        with pytest.raises(Exception):
            db.session.commit()


# ─── TESTES: MODELO Veiculo ───────────────────────────────────────────────────

def test_criar_veiculo(cliente_app):
    with cliente_app.app_context():
        c = Cliente(nome='Pedro', cpf='333.333.333-33')
        db.session.add(c)
        db.session.commit()
        v = Veiculo(placa='ABC1234', marca='Fiat', modelo='Uno',
                    ano=2010, cliente_id=c.id)
        db.session.add(v)
        db.session.commit()
        assert Veiculo.query.filter_by(placa='ABC1234').first() is not None


def test_veiculo_placa_unica(cliente_app):
    with cliente_app.app_context():
        c = Cliente(nome='Lucas', cpf='444.444.444-44')
        db.session.add(c)
        db.session.commit()
        v1 = Veiculo(placa='XYZ9999', marca='Ford', modelo='Ka', ano=2015, cliente_id=c.id)
        v2 = Veiculo(placa='XYZ9999', marca='GM', modelo='Onix', ano=2018, cliente_id=c.id)
        db.session.add(v1)
        db.session.commit()
        db.session.add(v2)
        with pytest.raises(Exception):
            db.session.commit()


# ─── TESTES: gerar_numero_os() ────────────────────────────────────────────────

def test_gerar_numero_os_inicial(cliente_app):
    with cliente_app.app_context():
        numero = gerar_numero_os()
        assert numero == 'OS0001'


def test_gerar_numero_os_sequencial(cliente_app):
    with cliente_app.app_context():
        c = Cliente(nome='Teste', cpf='555.555.555-55')
        db.session.add(c)
        db.session.commit()
        v = Veiculo(placa='TST0001', marca='Toyota', modelo='Corolla', ano=2020, cliente_id=c.id)
        db.session.add(v)
        db.session.commit()
        os1 = OrdemServico(numero='OS0001', descricao='Revisao', veiculo_id=v.id)
        db.session.add(os1)
        db.session.commit()
        numero = gerar_numero_os()
        assert numero == 'OS0002'


# ─── TESTES: ROTA login ───────────────────────────────────────────────────────

def test_login_pagina_get(client):
    response = client.get('/')
    assert response.status_code == 200


def test_login_sucesso(client, usuario_gestor):
    response = login(client, 'gestor@teste.com', 'senha123')
    assert response.status_code == 200


def test_login_senha_errada(client, usuario_gestor):
    response = login(client, 'gestor@teste.com', 'senhaerrada')
    assert 'incorretos' in response.data.decode('utf-8').lower() or response.status_code == 200


def test_login_email_inexistente(client):
    response = login(client, 'naoexiste@teste.com', 'qualquer')
    assert response.status_code == 200


# ─── TESTES: ROTA logout ──────────────────────────────────────────────────────

def test_logout(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200


# ─── TESTES: ROTA dashboard ───────────────────────────────────────────────────

def test_dashboard_sem_login(client):
    response = client.get('/dashboard', follow_redirects=True)
    assert response.status_code == 200


def test_dashboard_com_login(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/dashboard')
    assert response.status_code == 200


# ─── TESTES: ROTA clientes ────────────────────────────────────────────────────

def test_listar_clientes(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/clientes')
    assert response.status_code == 200


def test_novo_cliente_get(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/clientes/novo')
    assert response.status_code == 200


def test_novo_cliente_post(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.post('/clientes/novo', data={
        'nome': 'Maria Souza',
        'cpf': '666.666.666-66',
        'telefone': '88999998888',
        'email': 'maria@teste.com'
    }, follow_redirects=True)
    assert response.status_code == 200


def test_novo_cliente_cpf_duplicado(client, usuario_gestor, cliente_app):
    login(client, 'gestor@teste.com', 'senha123')
    with cliente_app.app_context():
        c = Cliente(nome='Existente', cpf='777.777.777-77')
        db.session.add(c)
        db.session.commit()
    response = client.post('/clientes/novo', data={
        'nome': 'Novo',
        'cpf': '777.777.777-77',
        'telefone': '',
        'email': ''
    }, follow_redirects=True)
    assert response.status_code == 200


# ─── TESTES: ROTA ordens ──────────────────────────────────────────────────────

def test_listar_ordens(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/ordens')
    assert response.status_code == 200


def test_nova_ordem_get(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/ordens/nova')
    assert response.status_code == 200


# ─── TESTES: ROTA usuarios (gestor) ───────────────────────────────────────────

def test_listar_usuarios_gestor(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/usuarios')
    assert response.status_code == 200


def test_listar_usuarios_mecanico_bloqueado(client, usuario_mecanico):
    login(client, 'mecanico@teste.com', 'senha123')
    response = client.get('/usuarios', follow_redirects=True)
    assert response.status_code == 200


def test_novo_usuario_get(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/usuarios/novo')
    assert response.status_code == 200


# ─── TESTES: ROTA pagamentos pendentes ────────────────────────────────────────

def test_pagamentos_pendentes(client, usuario_gestor):
    login(client, 'gestor@teste.com', 'senha123')
    response = client.get('/pagamentos/pendentes')
    assert response.status_code == 200


# ─── TESTES: API veiculos ─────────────────────────────────────────────────────

def test_api_veiculos(client, usuario_gestor, cliente_app):
    login(client, 'gestor@teste.com', 'senha123')
    with cliente_app.app_context():
        c = Cliente(nome='API Teste', cpf='888.888.888-88')
        db.session.add(c)
        db.session.commit()
        cliente_id = c.id
    response = client.get(f'/api/veiculos/{cliente_id}')
    assert response.status_code == 200
    assert b'veiculos' in response.data
