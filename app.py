import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from banco_dados import Residuo, Licenca

# --- NOVAS IMPORTAÇÕES PARA USAR O SEU TOKEN.JSON (OAUTH) ---
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 1. CONFIGURAÇÃO INICIAL
st.set_page_config(page_title="SIGA - Artemp", layout="wide")

engine = create_engine('sqlite:///artemp_siga.db', echo=False)
Session = sessionmaker(bind=engine)
session = Session()

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
menu = st.sidebar.radio("Navegação:", ["📊 Dashboard", "📝 Lançamentos", "📅 Licenças", "📂 Gestão Documental"])

# ==========================================
# PÁGINA 1: DASHBOARD
# ==========================================
if menu == "📊 Dashboard":
    st.title("📊 Painel de Indicadores Ambientais")
    
    st.write("### 🔍 Filtrar Período de Consulta")
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        mes_escolhido_nome = st.selectbox("Selecione o Mês:", NOMES_MESES, index=hoje.month - 1)
        mes_escolhido_num = NOMES_MESES.index(mes_escolhido_nome) + 1
        
    with col_filtro2:
        ano_escolhido = st.selectbox("Selecione o Ano:", [ano_atual, ano_atual - 1])

    if not df.empty:
        df_mes = df[(df['Data de Registro'].dt.month == mes_escolhido_num) & (df['Data de Registro'].dt.year == ano_escolhido)]
        total_mes = df_mes['Peso (kg)'].sum()
    else:
        total_mes = 0.0

    licencas_criticas = sum(1 for lic in todas_licencas if (lic.data_vencimento - hoje).days <= 30)

    col1, col2, col3 = st.columns(3)
    col1.metric(f"Gerado em {mes_escolhido_nome}/{ano_escolhido}", f"{total_mes:.1f} kg")
    col2.metric("Total Histórico Acumulado", f"{df['Peso (kg)'].sum():.1f} kg" if not df.empty else "0.0 kg")
    col3.metric("⚠️ Licenças Críticas", str(licencas_criticas))

    st.divider()

    if not df.empty:
        st.write("#### Distribuição por Classe (Histórico Geral)")
        peso_por_classe = df.groupby("Classe")["Peso (kg)"].sum().reset_index()
        mapa_cores = {"Classe I": "#1f77b4", "Classe II-A": "#28a745", "Classe II-B": "#ffc107"}
        peso_por_classe["Cor"] = peso_por_classe["Classe"].map(mapa_cores)
        
        st.bar_chart(peso_por_classe, x="Classe", y="Peso (kg)", color="Cor", horizontal=True)

        st.divider()
        st.write("#### 📥 Exportar Inventário")
        
        csv_dados = df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📄 Baixar Relatório Completo (CSV)", 
            data=csv_dados, 
            file_name="inventario_artemp.csv", 
            mime="text/csv"
        )

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
                        nome=nome_input, classe_nbr=classe_input, 
                        quantidade_kg=peso_input, setor_origem=setor_input, data_registro=data_input
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
                        residuo_alterar.status_logistica = novo_status
                        residuo_alterar.numero_mtr = mtr_input
                        session.commit()
                        st.success("Dados atualizados com sucesso!")
                with col_btn2:
                    if st.checkbox("Confirmar exclusão permanente"):
                        if st.button("🗑️ Eliminar", type="primary", use_container_width=True):
                            session.delete(residuo_alterar)
                            session.commit()
                            st.success("Eliminado!")

# ==========================================
# PÁGINA 3: LICENÇAS
# ==========================================
elif menu == "📅 Licenças":
    st.title("📅 Controle de Conformidade Legal")
    if not todas_licencas:
        st.info("Nenhuma licença cadastrada.")
    else:
        for lic in todas_licencas:
            dias_restantes = (lic.data_vencimento - hoje).days
            data_formatada = lic.data_vencimento.strftime("%d/%m/%Y")
            mensagem = f"**{lic.nome_documento}** ({lic.orgao_emissor}) - Vence em: {data_formatada} ({dias_restantes} dias restantes)"
            if dias_restantes < 0: st.error(f"🚨 VENCIDA! {mensagem}")
            elif dias_restantes <= 15: st.error(f"🔴 CRÍTICO: {mensagem}")
            elif dias_restantes <= 30: st.warning(f"🟡 ATENÇÃO: {mensagem}")
            else: st.success(f"🟢 REGULAR: {mensagem}")

# ==========================================
# PÁGINA 4: GESTÃO DOCUMENTAL E UPLOADS
# ==========================================
elif menu == "📂 Gestão Documental":
    st.title("📂 Central de Documentos (SGI e Operação)")
    
    # IMPORTANTE: Coloque os IDs reais das suas pastas do Drive aqui
    PASTAS_DRIVE = {
        "Procedimentos (SGI)": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl",
        "FISPQ / FDS": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl",
        "Notas Fiscais / MTRs": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl",
        "Treinamentos": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl"
    }

    # --- FUNÇÃO ATUALIZADA: COPIE E SUBSTITUA ESTE BLOCO INTEIRO ---
    def fazer_upload_drive(arquivo_bytes, nome_arquivo, mimetype, id_pasta_destino):
        SCOPES = ['https://www.googleapis.com/auth/drive']
        
        # O novo bloco entra exatamente aqui, respeitando os espaços de recuo:
        import json
        if "google" in st.secrets:
            # Se estiver rodando na nuvem do Streamlit (lê do painel da internet)
            token_info = json.loads(st.secrets["google"]["token"])
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        else:
            # Se estiver rodando localmente no seu computador (lê o arquivo físico do PC)
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # O restante da função continua igual:
        servico = build('drive', 'v3', credentials=creds)
        
        metadados = {
            'name': nome_arquivo,
            'parents': [id_pasta_destino]
        }
        
        media = MediaIoBaseUpload(arquivo_bytes, mimetype=mimetype, resumable=True)
        
        arquivo_criado = servico.files().create(body=metadados, media_body=media, fields='id').execute()
        return arquivo_criado.get('id')
    # ------------------------------------------------------------------------
    # ------------------------------------------------------------------------

    with st.form("form_upload_drive"):
        categoria = st.selectbox("Categoria do Documento:", list(PASTAS_DRIVE.keys()))
        arquivo_enviado = st.file_uploader("Selecione o arquivo", type=['pdf', 'png', 'jpg', 'jpeg'])
        
        btn_enviar = st.form_submit_button("📤 Enviar para Nuvem")
        
        if btn_enviar:
            if arquivo_enviado is not None:
                id_destino = PASTAS_DRIVE[categoria]
                nome_arquivo = arquivo_enviado.name
                mimetype = arquivo_enviado.type
                
                with st.spinner(f"Enviando '{nome_arquivo}' para o Google Drive..."):
                    try:
                        id_gerado = fazer_upload_drive(arquivo_enviado, nome_arquivo, mimetype, id_destino)
                        st.success(f"Sucesso! Documento enviado. ID no Drive: {id_gerado}")
                    except Exception as e:
                        st.error(f"Erro ao enviar para o Drive: {e}")
            else:
                st.error("Por favor, anexe um documento antes de enviar.")

session.close()