from sqlalchemy import create_engine, Column, Integer, String, Float, Date
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

# 3. Executando a criação da tabela no arquivo físico

Base.metadata.create_all(engine)

# 4. Criando uma "sessão" para conseguirmos inserir e ler dados posteriormente

Session = sessionmaker(bind=engine)
session = Session()
print("Banco de dados 'artemp_siga.db' e tabela 'inventario_residuos' criados com sucesso!")
