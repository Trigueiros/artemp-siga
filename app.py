import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from banco_dados import Residuo, Licenca

# 1. CONFIGURAÇÃO INICIAL
st.set_page_config(page_title="SIGA - Artemp", layout="wide")

engine = create_engine('sqlite:///artemp_siga.db', echo=False)
Session = sessionmaker(bind=engine)
session = Session()

# Lista global de meses para o filtro visual
NOMES_MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# 2. BUSCA E PREPARAÇÃO DOS DADOS GERAIS
todos_residuos = session.query(Residuo).all()
todas_licencas = session.query(Licenca).all()

if todos_residuos:
    df = pd.DataFrame([{
        "ID": r.id, "Material": r.nome, "Classe": r.classe_nbr, 
        "Peso (kg)": r.quantidade_kg, "Status": r.status_logistica,
        "MTR (SINIR)": r.numero_mtr if r.numero_mtr else "Não Emitido",
        "Data de Registro": r.data_registro
    } for r in todos_residuos])
    df['Data de Registro'] = pd.to_datetime(df['Data de Registro'])
else:
    df = pd.DataFrame(columns=["ID", "Material", "Classe", "Peso (kg)", "Status", "MTR (SINIR)", "Data de Registro"])

hoje = date.today()
ano_atual = hoje.year

# 3. MENU LATERAL DE NAVEGAÇÃO
st.sidebar.title("🌱 SIGA - Artemp")
st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegação:", ["📊 Dashboard", "📝 Lançamentos", "📅 Licenças"])

# ==========================================
# PÁGINA 1: DASHBOARD
# ==========================================
if menu == "📊 Dashboard":
    st.title("📊 Painel de Indicadores Ambientais")
    
    # --- NOVA FUNCIONALIDADE: FILTRO DINÂMICO DE TEMPO ---
    st.write("### 🔍 Filtrar Período de Consulta")
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        # O 'index=hoje.month - 1' faz o sistema inicializar apontando automaticamente para o mês atual
        mes_escolhido_nome = st.selectbox("Selecione o Mês:", NOMES_MESES, index=hoje.month - 1)
        # Descobre o número do mês (ex: "Junho" vira 6)
        mes_escolhido_num = NOMES_MESES.index(mes_escolhido_nome) + 1
        
    with col_filtro2:
        ano_escolhido = st.selectbox("Selecione o Ano:", [ano_atual, ano_atual - 1])

    # Cálculo do Totalizador Mensal com base no filtro do usuário
    if not df.empty:
        df_mes = df[(df['Data de Registro'].dt.month == mes_escolhido_num) & (df['Data de Registro'].dt.year == ano_escolhido)]
        total_mes = df_mes['Peso (kg)'].sum()
    else:
        total_mes = 0.0

    licencas_criticas = sum(1 for lic in todas_licencas if (lic.data_vencimento - hoje).days <= 30)

    # Cartões Superiores (O rótulo do primeiro cartão agora muda de nome dinamicamente!)
    col1, col2, col3 = st.columns(3)
    col1.metric(f"Gerado em {mes_escolhido_nome}/{ano_escolhido}", f"{total_mes:.1f} kg")
    col2.metric("Total Histórico Acumulado", f"{df['Peso (kg)'].sum():.1f} kg" if not df.empty else "0.0 kg")
    col3.metric("⚠️ Licenças Críticas", str(licencas_criticas))

    st.divider()

    # Gráfico baseado em todos os dados ou dados filtrados (opcional, mantido geral por classe)
    if not df.empty:
        st.write("#### Distribuição por Classe (Histórico Geral)")
        peso_por_classe = df.groupby("Classe")["Peso (kg)"].sum().reset_index()
        mapa_cores = {"Classe I": "#1f77b4", "Classe II-A": "#28a745", "Classe II-B": "#ffc107"}
        peso_por_classe["Cor"] = peso_por_classe["Classe"].map(mapa_cores)
        st.bar_chart(peso_por_classe, x="Classe", y="Peso (kg)", color="Cor", horizontal=True)

# ==========================================
# PÁGINA 2: LANÇAMENTOS
# ==========================================
elif menu == "📝 Lançamentos":
    st.title("📝 Gestão do Inventário")
    
    with st.expander("➕ Adicionar Novo Resíduo (Permite Retroagir Data)", expanded=False):
        with st.form("form_novo_residuo"):
            col_f1, col_f2 = st.columns(2)
            nome_input = col_f1.text_input("Nome do Material")
            classe_input = col_f1.selectbox("Classe NBR", ["Classe I", "Classe II-A", "Classe II-B"])
            
            peso_input = col_f2.number_input("Peso (kg)", min_value=0.0, step=0.5)
            setor_input = col_f2.text_input("Setor de Origem")
            
            data_input = st.date_input("Data Real da Geração do Resíduo", date.today())
            
            if st.form_submit_button("Registrar Entrada"):
                if nome_input and setor_input:
                    novo = Residuo(
                        nome=nome_input, 
                        classe_nbr=classe_input, 
                        quantidade_kg=peso_input, 
                        setor_origem=setor_input,
                        data_registro=data_input
                    )
                    session.add(novo)
                    session.commit()
                    st.success("Resíduo registrado com sucesso!")
                else:
                    st.error("Preencha todos os campos.")

    st.write("### Inventário Atual")
    if not df.empty:
        df_visual = df.copy()
        df_visual['Data de Registro'] = df_visual['Data de Registro'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_visual, use_container_width=True, hide_index=True)
        
        st.divider()
        
        st.write("#### 🔧 Atualizar Status Operacional ou MTR (SINIR)")
        lista_ids = df["ID"].tolist()
        col_id, col_acao = st.columns([1, 3])
        
        with col_id:
            id_selecionado = st.selectbox("Selecione o ID", lista_ids)
            
        residuo_alterar = session.query(Residuo).filter_by(id=id_selecionado).first()
        
        if residuo_alterar:
            with col_acao:
                estados_possiveis = ["Armazenado", "MTR Emitido (Aguardando CDF)", "Com CDF"]
                try:
                    indice_atual = estados_possiveis.index(residuo_alterar.status_logistica)
                except:
                    indice_atual = 0
                    
                novo_status = st.selectbox("Alterar Estado Logístico para:", estados_possiveis, index=indice_atual)
                
                mtr_input = residuo_alterar.numero_mtr
                if novo_status in ["MTR Emitido (Aguardando CDF)", "Com CDF"]:
                    mtr_input = st.text_input("Digite o Número do MTR gerado no SINIR:", value=residuo_alterar.numero_mtr or "")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Salvar Alterações", use_container_width=True):
                        residuo_alterar.status_logistica = FilteredStatus = novo_status
                        residuo_alterar.numero_mtr = mtr_input
                        session.commit()
                        st.success("Dados atualizados com sucesso!")
                with col_btn2:
                    if st.checkbox("Confirmar exclusão permanente"):
                        if st.button("🗑️ Eliminar", type="primary", use_container_width=True):
                            session.delete(residuo_alterar)
                            session.commit()
                            st.success("Eliminado!")
    else:
        st.info("Nenhum material no inventário.")

# ==========================================
# PÁGINA 3: LICENÇAS
# ==========================================
elif menu == "📅 Licenças":
    st.title("📅 Controle de Conformidade Legal")
    if not todas_licencas:
        st.info("Nenhuma licença cadastrada. Execute o script 'inserir_licencas.py' caso queira reinserir os testes.")
    else:
        for lic in todas_licencas:
            dias_restantes = (lic.data_vencimento - hoje).days
            data_formatada = lic.data_vencimento.strftime("%d/%m/%Y")
            mensagem = f"**{lic.nome_documento}** ({lic.orgao_emissor}) - Vence em: {data_formatada} ({dias_restantes} dias restantes)"
            if dias_restantes < 0: st.error(f"🚨 VENCIDA! {mensagem}")
            elif dias_restantes <= 15: st.error(f"🔴 CRÍTICO: {mensagem}")
            elif dias_restantes <= 30: st.warning(f"🟡 ATENÇÃO: {mensagem}")
            else: st.success(f"🟢 REGULAR: {mensagem}")

session.close()