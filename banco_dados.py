from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import date

# 1. Configurando o banco de dados (será criado um arquivo .db na sua pasta)
engine = create_engine('sqlite:///artemp_siga.db', echo=False)
Base = declarative_base()

# 2. Criando a estrutura da nossa tabela de Inventário de Resíduos

class Residuo(Base):
    __tablename__= 'inventario_residuos'

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False) # Ex: Sucata de Cobre, Óleo Lubrificante Usado
    classe_nbr = Column(String, nullable=False) # Ex: Classe I, Classe II-A
    quantidade_kg = Column(Float, nullable=False)
    setor_origem = Column(String, nullable=False) # Ex: Manutenção, Obra Externa
    status_logistica = Column(String, default="Armazenado") # Armazenado, MTR Emitido, Com CDF
    numero_mtr = Column(String, nullable=True) # <-- NOVA COLUNA PARA O SINIR
    data_registro = Column(Date, default=date.today)

    def __repr__(self):
        return f"<Resíduo: {self.nome} | {self.quantidade_kg}kg | Status: {self.status_logistica}>"

# Adicione esta nova tabela ao banco_dados.py (Validade das Licenças)
class Licenca(Base):
    __tablename__ = 'controle_licencas'

    id = Column(Integer, primary_key=True)
    nome_documento = Column(String, nullable=False)
    orgao_emissor = Column(String, nullable=False) # Ex: INEMA, SEDUR, LIMPURB, IBAMA
    data_vencimento = Column(Date, nullable=False)
    
    def __repr__(self):
        return f"<Licença: {self.nome_documento} | Vence em: {self.data_vencimento}>"

# --- NOVA TABELA: USUÁRIOS DO ERP ---
class Usuario(Base):
    __tablename__ = 'usuarios_sistema'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False) # Ex: s.trigueiros
    senha_hash = Column(String, nullable=False)            # Senha protegida
    nome_completo = Column(String, nullable=False)
    cargo = Column(String, default="Operador")             # Ex: Gerente, Almoxarife
    modulos_acesso = Column(String, default="📊 Dashboard")

# --- NOVA TABELA: TRATAMENTO DE NÃO CONFORMIDADES (SGI) ---
class NaoConformidade(Base):
    __tablename__ = 'nao_conformidades'
    id = Column(Integer, primary_key=True)
    descricao = Column(String, nullable=False)      # O que aconteceu de errado?
    acao_proposta = Column(String, nullable=False)  # Como vamos resolver?
    responsavel = Column(String, nullable=False)    # Quem vai executar?
    data_registro = Column(Date, default=date.today) # Quando foi identificada?
    prazo_limite = Column(Date, nullable=False)     # Cronograma (Data Alvo)
    status = Column(String, default="Aberta")       # Aberta, Em Andamento, Concluída
    setor_origem = Column(String, default="Não Informado") # Onde ocorreu a falha
    gravidade = Column(String, default="Moderada")         # Leve, Moderada, Crítica

Base.metadata.create_all(engine)
print("Tabela de usuários do ERP criada com sucesso!")

# --- NOVA TABELA: ALMOXARIFADO E ESTOQUE ---
class Estoque(Base):
    __tablename__ = 'controle_estoque'
    id = Column(Integer, primary_key=True)
    nome_material = Column(String, nullable=False)
    categoria = Column(String, nullable=False)      # Ex: EPI, Insumo Químico, Ferramenta
    quantidade = Column(Float, nullable=False)      # Saldo atual
    unidade_medida = Column(String, nullable=False) # Ex: un, kg, L, cx
    fornecedor = Column(String, nullable=False)
    nota_fiscal = Column(String, nullable=True)     # Opcional
    data_entrada = Column(Date, default=date.today)
    custo_medio = Column(Float, default=0.0)        # <-- NOVA COLUNA: VALOR DA UNIDADE
    
    # --- NOVAS COLUNAS PARA CONTROLE DE QUALIDADE E SGI ---
    data_validade = Column(Date, nullable=True)    # Prazo de validade do insumo
    status_fispq = Column(String, default="Não se aplica") # Regulamentação técnica

print("Tabela de Estoque criada com sucesso!")

# --- NOVA TABELA: HISTÓRICO DE ENTRADAS DE NOTAS FISCAIS ---
class EntradaNF(Base):
    __tablename__ = 'entradas_nota_fiscal'
    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, nullable=False)         # Aponta para o ID fixo do produto no Estoque
    numero_nf = Column(String, nullable=False)           # Número da Nota Fiscal corrente
    fornecedor = Column(String, nullable=False)
    quantidade_recebida = Column(Float, nullable=False)  # Qtd vinda nesta NF específica
    preco_unitario = Column(Float, nullable=False)   # <-- NOVA COLUNA: PREÇO NA NF
    data_recebimento = Column(Date, default=date.today)

# --- NOVA TABELA: GESTÃO ÁGIL (KANBAN) ---
class TarefaKanban(Base):
    __tablename__ = 'kanban_tarefas'
    id = Column(Integer, primary_key=True)
    titulo = Column(String, nullable=False)
    descricao = Column(String, nullable=True)
    responsavel = Column(String, nullable=False)
    prazo = Column(Date, nullable=False)
    status = Column(String, default="A Fazer") # A Fazer, Em Andamento, Concluída
    data_criacao = Column(Date, default=date.today)

# --- NOVAS TABELAS: MÓDULO DE PRODUÇÃO (MRP) ---
class OrdemProducao(Base):
    __tablename__ = 'ordens_producao'
    id = Column(Integer, primary_key=True)
    codigo_op = Column(String, unique=True, nullable=False)
    nome_produto = Column(String, nullable=False)
    quantidade_esperada = Column(Float, nullable=False)
    status = Column(String, default="Aberta") # Aberta, Em Produção, Concluída
    data_abertura = Column(Date, default=date.today)
    data_conclusao = Column(Date, nullable=True)
    custo_total = Column(Float, default=0.0)

class ConsumoOP(Base):
    __tablename__ = 'consumo_op'
    id = Column(Integer, primary_key=True)
    op_id = Column(Integer, nullable=False)
    material_id = Column(Integer, nullable=False)
    quantidade_consumida = Column(Float, nullable=False)
    custo_alocado = Column(Float, nullable=False)

# --- NOVO ESTOQUE: PRODUTOS ACABADOS ---
class ProdutoAcabado(Base):
    __tablename__ = 'estoque_produtos_acabados'
    id = Column(Integer, primary_key=True)
    codigo = Column(String, unique=True, nullable=False)
    descricao = Column(String, nullable=False)
    quantidade = Column(Float, default=0.0)
    custo_unitario = Column(Float, default=0.0)
    valor_total = Column(Float, default=0.0)
    data_ultima_entrada = Column(Date, default=date.today)


# --- NOVA TABELA: COMERCIAL E FATURAMENTO ---
class Venda(Base):
    __tablename__ = 'registro_vendas'
    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, nullable=False) # Refere-se ao ProdutoAcabado.id
    nome_produto = Column(String, nullable=False)
    cliente = Column(String, nullable=False)
    quantidade_vendida = Column(Float, nullable=False)
    preco_unitario_venda = Column(Float, nullable=False)
    valor_total_venda = Column(Float, nullable=False)
    custo_total_produto = Column(Float, nullable=False) # Para apuração do lucro (CMV)
    data_venda = Column(Date, default=date.today)

    # --- NOVAS COLUNAS FISCAIS ---
    status_fiscal = Column(String, default="Pendente") # Pendente, Emitida, Erro
    numero_nf = Column(String, nullable=True)          # Guardará o número da NFC-e/NF-e

# ==========================================
# NOVAS TABELAS: ENGENHARIA DE PRODUTO (MRP)
# ==========================================
class FichaTecnica(Base):
    __tablename__ = 'fichas_tecnicas'
    id = Column(Integer, primary_key=True)
    nome_receita = Column(String, nullable=False)
    rendimento = Column(Float, default=1.0) # Ex: Uma receita rende 50 trufas

class IngredienteFicha(Base):
    __tablename__ = 'ingredientes_ficha'
    id = Column(Integer, primary_key=True)
    ficha_id = Column(Integer, ForeignKey('fichas_tecnicas.id'))
    insumo_id = Column(Integer, ForeignKey('controle_estoque.id')) # <-- O NOME EXATO AQUI
    quantidade_usada = Column(Float)

# 3. Executando a criação da tabela no arquivo físico

Base.metadata.create_all(engine)

# 4. Criando uma "sessão" para conseguirmos inserir e ler dados posteriormente

Session = sessionmaker(bind=engine)
session = Session()
print("Banco de dados 'artemp_siga.db' e tabela 'inventario_residuos' criados com sucesso!")
