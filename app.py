import streamlit as st
import pandas as pd
import altair as alt
import hashlib
import json
from datetime import date
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
# Importamos a nova tabela NaoConformidade do banco de dados
from banco_dados import Residuo, Licenca, Usuario, NaoConformidade, Estoque, EntradaNF, TarefaKanban 

# Importações para o Google Drive
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 1. CONFIGURAÇÃO INICIAL
st.set_page_config(page_title="SIGA - Artemp", layout="wide")

engine = create_engine('sqlite:///artemp_siga.db', echo=False)
Session = sessionmaker(bind=engine)
session = Session()

def criptografar_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario_atual = ""
    st.session_state.cargo_atual = ""

NOMES_MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# =====================================================================
# TELA DE AUTENTICAÇÃO (SÓ APARECE SE NÃO ESTIVER LOGADO)
# =====================================================================
if not st.session_state.logado:
    st.title("🔐 SIGA - Portal de Acesso Corporativo")
    aba_login, aba_cadastro = st.tabs(["🔑 Acessar Sistema", "📝 Criar Usuário Local"])
    
    with aba_login:
        with st.form("form_login"):
            st.subheader("Login do Usuário")
            user_input = st.text_input("Usuário (Username)")
            senha_input = st.text_input("Senha", type="password")
            btn_entrar = st.form_submit_button("Entrar no ERP")
            
            if btn_entrar:
                hash_busca = criptografar_senha(senha_input)
                usuario_encontrado = session.query(Usuario).filter_by(username=user_input, senha_hash=hash_busca).first()
                if usuario_encontrado:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = usuario_encontrado.nome_completo
                    st.session_state.cargo_atual = usuario_encontrado.cargo
                    st.success(f"Acesso autorizado! Bem-vindo.")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
                    
    with aba_cadastro:
        with st.form("form_cadastro_usuario"):
            st.subheader("Registro de Novo Operador")
            novo_nome = st.text_input("Nome Completo")
            novo_username = st.text_input("Definir Nome de Usuário (Ex: j.silva)")
            nova_senha = st.text_input("Definir Senha", type="password")
            novo_cargo = st.selectbox("Cargo/Nível de Acesso:", ["Operador de Almoxarifado", "Supervisor de SGI", "Gerente de Operações","Técnico","Diretor","Assistente","Outros"])
            btn_cadastrar = st.form_submit_button("Salvar no Sistema")
            
            if btn_cadastrar:
                if novo_nome and novo_username and nova_senha:
                    usuario_existe = session.query(Usuario).filter_by(username=novo_username).first()
                    if usuario_existe:
                        st.error("Este nome de usuário já está em uso.")
                    else:
                        hash_seguro = criptografar_senha(nova_senha)
                        novo_usuario = Usuario(
                            username=novo_username, senha_hash=hash_seguro,
                            nome_completo=novo_nome, cargo=novo_cargo
                        )
                        session.add(novo_usuario)
                        session.commit()
                        st.success("Usuário cadastrado com sucesso! Faça login na primeira aba.")
                else:
                    st.error("Por favor, preencha todos os campos.")

# =====================================================================
# SISTEMA PRINCIPAL (SÓ CARREGA SE O PORTEIRO LIBERAR)
# =====================================================================
else:
    # BUSCA DOS DADOS GERAIS
    todos_residuos = session.query(Residuo).all()
    todas_licencas = session.query(Licenca).all()
    todas_ncs = session.query(NaoConformidade).all() # Nova busca de NCs

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

    # MENU LATERAL DE NAVEGAÇÃO
    st.sidebar.title("🌱 SIGA - Artemp")
    st.sidebar.write(f"👤 **Usuário:** {st.session_state.usuario_atual}")
    st.sidebar.caption(f"💼 **Perfil:** {st.session_state.cargo_atual}")
    
    if st.sidebar.button("🚪 Encerrar Sessão (Logout)", use_container_width=True):
        st.session_state.logado = False
        st.session_state.usuario_atual = ""
        st.session_state.cargo_atual = ""
        st.rerun()
        
    st.sidebar.markdown("---")
    # Adicionada a nova aba "⚠️ Não Conformidades" no menu
    menu = st.sidebar.radio("Navegação:", ["📊 Dashboard", "📝 Lançamentos", "📅 Licenças", "📂 Gestão Documental", "⚠️ Não Conformidades", "📦 Almoxarifado / Estoque", "📋 Kanban de Tarefas"])

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
            
            # Usamos o Altair para forçar a amarração exata (Domain = Range)
            grafico = alt.Chart(peso_por_classe).mark_bar().encode(
                x=alt.X("Peso (kg):Q", title="Peso (kg)"),
                y=alt.Y("Classe:N", title="Classe", sort=["Classe I", "Classe II-A", "Classe II-B"]),
                color=alt.Color(
                    "Classe:N",
                    scale=alt.Scale(
                        domain=["Classe I", "Classe II-A", "Classe II-B"], # A Classe...
                        range=["#ff2d2d", "#00e73a", "#ffc107"]             # ...recebe esta cor exata.
                    ),
                    legend=None # Esconde a legenda para o painel ficar mais limpo
                )
            )
            st.altair_chart(grafico, use_container_width=True)

    # ==========================================
    # PÁGINA 2: LANÇAMENTOS
    # ==========================================
    elif menu == "📝 Lançamentos":
        st.title("📝 Gestão do Inventário")
        with st.expander("➕ Adicionar Novo Resíduo", expanded=False):
            with st.form("form_novo_residuo"):
                col_f1, col_f2 = st.columns(2)
                nome_input = col_f1.text_input("Nome do Material")
                classe_input = col_f1.selectbox("Classe NBR", ["Classe I", "Classe II-A", "Classe II-B"])
                peso_input = col_f2.number_input("Peso (kg)", min_value=0.0, step=0.5)
                setor_input = col_f2.text_input("Setor de Origem")
                data_input = st.date_input("Data Real da Geração do Resíduo", date.today())
                
                if st.form_submit_button("Registrar Entrada"):
                    if nome_input and setor_input:
                        novo = Residuo(nome=nome_input, classe_nbr=classe_input, quantidade_kg=peso_input, setor_origem=setor_input, data_registro=data_input)
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
                    try: indice_atual = estados_possiveis.index(residuo_alterar.status_logistica)
                    except: indice_atual = 0
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
        else:
            st.info("Nenhum material no inventário.")

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
        PASTAS_DRIVE = {
            "Procedimentos (SGI)": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl",
            "FISPQ / FDS": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl",
            "Notas Fiscais / MTRs": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl",
            "Treinamentos": "1R7KGqBFMMkdM0ONp5kHkswS138dVEIbl"
        }

        def fazer_upload_drive(arquivo_bytes, nome_arquivo, mimetype, id_pasta_destino):
            SCOPES = ['https://www.googleapis.com/auth/drive']
            if "google" in st.secrets:
                token_info = json.loads(st.secrets["google"]["token"])
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            else:
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            servico = build('drive', 'v3', credentials=creds)
            metadados = {'name': nome_arquivo, 'parents': [id_pasta_destino]}
            media = MediaIoBaseUpload(arquivo_bytes, mimetype=mimetype, resumable=True)
            arquivo_criado = servico.files().create(body=metadados, media_body=media, fields='id').execute()
            return arquivo_criado.get('id')

        with st.form("form_upload_drive"):
            categoria = st.selectbox("Categoria do Documento:", list(PASTAS_DRIVE.keys()))
            arquivo_enviado = st.file_uploader("Selecione o arquivo", type=['pdf', 'png', 'jpg', 'jpeg'])
            btn_enviar = st.form_submit_button("📤 Enviar para Nuvem")
            
            if btn_enviar:
                if arquivo_enviado is not None:
                    id_destino = PASTAS_DRIVE[categoria]
                    nome_arquivo = arquivo_enviado.name
                    mimetype = arquivo_enviado.type
                    with st.spinner(f"Enviando '{nome_arquivo}'..."):
                        try:
                            id_gerado = fazer_upload_drive(arquivo_enviado, nome_arquivo, mimetype, id_destino)
                            st.success(f"Sucesso! Documento enviado. ID no Drive: {id_gerado}")
                        except Exception as e: st.error(f"Erro ao enviar para o Drive: {e}")
                else: st.error("Por favor, anexe um documento.")

  # ==========================================
    # PÁGINA 5: NÃO CONFORMIDADES (COM PARETO)
    # ==========================================
    elif menu == "⚠️ Não Conformidades":
        st.title("⚠️ Tratamento de Não Conformidades e Matriz de Risco")
        
        # 1. FORMULÁRIO DE CADASTRO DE NC COM MATRIZ DE RISCO
        with st.expander("➕ Registrar Nova Não Conformidade (RNC)", expanded=False):
            with st.form("form_nova_nc"):
                st.subheader("Evidência e Classificação do Desvio")
                
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    setor_input = st.selectbox("Setor de Origem do Desvio:", ["Almoxarifado", "Operação/Campo", "SGI/Qualidade", "Manutenção", "Administrativo"])
                    gravidade_input = st.selectbox("Gravidade (Impacto no Negócio):", ["Leve", "Moderada", "Crítica"])
                with col_r2:
                    data_detecao = st.date_input("Data de Identificação", date.today())
                    prazo_input = st.date_input("Cronograma - Prazo Limite:", date.today() + pd.Timedelta(days=7))
                
                desc_input = st.text_area("Descrição Ocorrência / Desvio encontrado:")
                
                col_nc1, col_nc2 = st.columns(2)
                with col_nc1:
                    acao_input = st.text_area("Plano de Ação (Correção Imediata/Preventiva):")
                with col_nc2:
                    responsavel_input = st.text_input("Colaborador Responsável pela Execução:")
                
                btn_salvar_nc = st.form_submit_button("Emitir Relatório de Não Conformidade")
                
                if btn_salvar_nc:
                    if desc_input and acao_input and responsavel_input:
                        nova_nc = NaoConformidade(
                            descricao=desc_input, acao_proposta=acao_input,
                            responsavel=responsavel_input, data_registro=data_detecao,
                            prazo_limite=prazo_input, status="Aberta",
                            setor_origem=setor_input, gravidade=gravidade_input
                        )
                        session.add(nova_nc)
                        session.commit()
                        st.success("Não Conformidade registrada e inserida na Matriz de Risco!")
                        st.rerun()
                    else:
                        st.error("Por favor, preencha os campos de descrição, ação e responsável.")

        st.divider()

        if todas_ncs:
            # 2. DASHBOARD DE INTELIGÊNCIA DE QUALIDADE (PARETO)
            st.write("### 📊 Análise de Pareto (Desvios por Setor)")
            
            # Converte os dados do banco para um DataFrame Pandas
            df_ncs = pd.DataFrame([{
                "Setor": n.setor_origem,
                "Gravidade": n.gravidade,
                "Status": n.status
            } for n in todas_ncs])
            
            # Conta a frequência de RNCs por setor e ordena do maior para o menor
            pareto_df = df_ncs.groupby("Setor").size().reset_index(name='Frequência')
            pareto_df = pareto_df.sort_values(by='Frequência', ascending=False)
            
            # Cria o gráfico de barras ordenado usando Altair
            grafico_pareto = alt.Chart(pareto_df).mark_bar(color='#1f77b4').encode(
                x=alt.X("Setor:N", sort='-y', title="Setor de Origem"),
                y=alt.Y("Frequência:Q", title="Número de Não Conformidades"),
                tooltip=['Setor', 'Frequência']
            ).properties(height=300)
            
            st.altair_chart(grafico_pareto, use_container_width=True)
            
            st.divider()
            
            # 3. QUADRO GERAL E BUSCA
            st.write("### 📋 Quadro de Planos de Ação")
            
            dados_nc_df = pd.DataFrame([{
                "Código RNC": f"RNC-{n.id:05d}",
                "Setor": n.setor_origem,
                "Gravidade": n.gravidade,
                "Descrição do Desvio": n.descricao,
                "Responsável": n.responsavel,
                "Prazo Final": n.prazo_limite.strftime('%d/%m/%Y'),
                "Status": n.status
            } for n in todas_ncs])
            
            # Aplica formatação de cores na tabela para a Gravidade
            def colorir_gravidade(val):
                color = '#ff4b4b' if val == 'Crítica' else '#ffa500' if val == 'Moderada' else '#00cc66'
                return f'color: {color}; font-weight: bold'
            
            st.dataframe(dados_nc_df.style.map(colorir_gravidade, subset=['Gravidade']), use_container_width=True, hide_index=True)
            
            # 4. BUSCA E ATUALIZAÇÃO INTELIGENTE
            st.write("#### 🔍 Buscar e Atualizar RNC")
            busca_rnc = st.text_input("🔎 Digite o Código numérico da RNC para atualizar (Ex: 1):")
            
            if busca_rnc:
                id_str = "".join(filter(str.isdigit, busca_rnc))
                if id_str:
                    id_busca = int(id_str)
                    nc_alterar = session.query(NaoConformidade).filter_by(id=id_busca).first()
                    
                    if nc_alterar:
                        with st.container(border=True):
                            st.write(f"**RNC-{nc_alterar.id:05d} | {nc_alterar.setor_origem} | Risco: {nc_alterar.gravidade}**")
                            st.write(f"**Falha:** {nc_alterar.descricao}")
                            
                            status_opcoes = ["Aberta", "Em Andamento", "Tratada", "Concluída"]
                            try: idx_status_nc = status_opcoes.index(nc_alterar.status)
                            except: idx_status_nc = 0
                            
                            novo_status_nc = st.selectbox("Atualizar Status da Ação:", status_opcoes, index=idx_status_nc)
                            
                            col_nc_btn1, col_nc_btn2 = st.columns(2)
                            with col_nc_btn1:
                                if st.button("🔄 Salvar Atualização", use_container_width=True):
                                    nc_alterar.status = novo_status_nc
                                    session.commit()
                                    st.success("RNC atualizada!")
                                    st.rerun()
                            with col_nc_btn2:
                                if st.checkbox("Confirmar exclusão"):
                                    if st.button("🗑️ Deletar Registro", type="primary", use_container_width=True):
                                        session.delete(nc_alterar)
                                        session.commit()
                                        st.success("Removido!")
                                        st.rerun()
                    else:
                        st.error("RNC não encontrada.")
        else:
            st.info("Nenhuma Não Conformidade registrada no momento.")

# ==========================================
    # PÁGINA 6: ALMOXARIFADO / ESTOQUE (SGI)
    # ==========================================
    elif menu == "📦 Almoxarifado / Estoque":
        st.title("📦 Almoxarifado, Valoração & Controle de Conformidade Química")
        
        todos_produtos = session.query(Estoque).all()
        todas_nfs = session.query(EntradaNF).all()
        
        # --- SISTEMA DE ALERTAS AUTOMÁTICOS DE SEGURANÇA (SGI) ---
        itens_vencidos = []
        fispq_pendentes = []
        total_patrimonio = 0.0
        
        if todos_produtos:
            for p in todos_produtos:
                total_patrimonio += (p.quantidade * p.custo_medio)
                # Verifica criticidade de validade para Insumos Químicos ou EPIs
                if p.data_validade and p.data_validade < hoje and p.quantidade > 0:
                    itens_vencidos.append(p)
                # Verifica documentação de segurança exigida por norma
                if p.categoria == "Insumos Químicos" and p.status_fispq in ["Pendente", "Desatualizada"]:
                    fispq_pendentes.append(p)
        
        # KPIs de Controle Financeiro e de Risco
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        col_kpi1.metric(label="💰 Capital Imobilizado", value=f"R$ {total_patrimonio:,.2f}")
        col_kpi2.metric(label="🚨 Produtos Vencidos em Estoque", value=str(len(itens_vencidos)))
        col_kpi3.metric(label="📄 Alertas de FISPQ/FDS Pendentes", value=str(len(fispq_pendentes)))
        
        # Exibição visual dos alertas do SGI
        if itens_vencidos:
            for item in itens_vencidos:
                st.error(f"🚨 **PRODUTO VENCIDO EM ESTOQUE:** O item **MAT-{item.id:04d} | {item.nome_material}** está com o prazo de validade expirado desde {item.data_validade.strftime('%d/%m/%Y')}. Bloqueie o uso operacional imediato!")
                
        if fispq_pendentes:
            for item in fispq_pendentes:
                st.warning(f"⚠️ **ALERTA DOCUMENTAL SGI:** O insumo **MAT-{item.id:04d} | {item.nome_material}** está operando com FISPQ/FDS **{item.status_fispq}**. Regularize junto ao fornecedor para evitar desvios em auditorias.")
        
        st.divider()
        
        # 2. FORMULÁRIO DE RECEBIMENTO DE NOTA FISCAL COM CRITÉRIOS DE QUALIDADE
        with st.expander("🧾 Registrar Entrada de Nota Fiscal (Recebimento)", expanded=False):
            tipo_entrada = st.radio(
                "O material desta Nota Fiscal já possui cadastro no estoque?", 
                ["Sim, produto já cadastrado", "Não, é um produto novo"]
            )
            
            with st.form("form_entrada_nf"):
                st.subheader("Dados Documentais da NF")
                col_nf1, col_nf2 = st.columns(2)
                
                with col_nf1:
                    nf_numero = st.text_input("Número da Nota Fiscal (NF-e):")
                    fornecedor_input = st.text_input("Fornecedor / Emitente:")
                    qtd_recebida = st.number_input("Quantidade Recebida:", min_value=0.0, step=1.0)
                    preco_unitario_input = st.number_input("Preço Unitário na NF (R$):", min_value=0.0, step=0.01)
                    data_recebimento = st.date_input("Data de Entrada Física:", date.today())
                
                with col_nf2:
                    st.subheader("Vínculo & Parâmetros Técnicos")
                    if tipo_entrada == "Sim, produto já cadastrado":
                        if todos_produtos:
                            opcoes_produtos = [f"MAT-{p.id:04d} | {p.nome_material}" for p in todos_produtos]
                            produto_selecionado = st.selectbox("Selecione o Produto Destino:", opcoes_produtos)
                            nome_novo, cat_nova, und_nova = "", "", ""
                        else:
                            st.warning("Nenhum produto cadastrado ainda. Mude para 'Produto Novo'.")
                            produto_selecionado = None
                        
                        # Campos para atualizar lote corrente na entrada
                        validade_lote = st.date_input("Atualizar Validade deste lote (Opcional):", date.today() + pd.Timedelta(days=365))
                        fispq_lote = st.selectbox("Atualizar Status FISPQ/FDS:", ["Não se aplica", "Regular", "Pendente", "Desatualizada"])
                    else:
                        nome_novo = st.text_input("Nome do Novo Material / Produto:")
                        cat_nova = st.selectbox("Categoria:", ["EPI (Equip. Proteção)", "Insumos Químicos", "Ferramentas", "Peças de Reposição", "Outros"])
                        und_nova = st.selectbox("Unidade de Medida:", ["Unidade (un)", "Quilograma (kg)", "Litro (L)", "Caixa (cx)"])
                        
                        # Parâmetros de conformidade obrigatórios para novos cadastros
                        validade_lote = st.date_input("Data de Validade do Produto:", date.today() + pd.Timedelta(days=365))
                        fispq_lote = st.selectbox("Status inicial da FISPQ/FDS:", ["Não se aplica", "Regular", "Pendente", "Desatualizada"])
                        produto_selecionado = None
                
                btn_processar_nf = st.form_submit_button("⚙️ Processar Entrada Fiscal & Validar Critérios")
                
                if btn_processar_nf:
                    if nf_numero and fornecedor_input and qtd_recebida > 0 and preco_unitario_input > 0:
                        
                        # CENÁRIO A: Produto já cadastrado
                        if tipo_entrada == "Sim, produto já cadastrado" and produto_selecionado:
                            id_produto = int(produto_selecionado.split("|")[0].split("-")[1])
                            produto_bd = session.query(Estoque).filter_by(id=id_produto).first()
                            
                            if produto_bd:
                                # Recálculo do Custo Médio Ponderado
                                valor_estoque_atual = produto_bd.quantidade * produto_bd.custo_medio
                                valor_nova_nf = qtd_recebida * preco_unitario_input
                                nova_qtd_total = produto_bd.quantidade + qtd_recebida
                                novo_custo_medio = (valor_estoque_atual + valor_nova_nf) / nova_qtd_total
                                
                                # Atualiza dados mestres e critérios técnicos
                                produto_bd.quantidade = nova_qtd_total
                                produto_bd.custo_medio = novo_custo_medio
                                produto_bd.data_validade = validade_lote
                                produto_bd.status_fispq = fispq_lote
                                
                                nova_nota = EntradaNF(
                                    produto_id=produto_bd.id, numero_nf=nf_numero,
                                    fornecedor=fornecedor_input, quantidade_recebida=qtd_recebida,
                                    preco_unitario=preco_unitario_input, data_recebimento=data_recebimento
                                )
                                session.add(nova_nota)
                                session.commit()
                                st.success(f"Nota Fiscal {nf_numero} integrada ao estoque do material {produto_bd.nome_material}!")
                                st.rerun()
                        
                        # CENÁRIO B: Novo produto
                        elif tipo_entrada == "Não, é um produto novo" and nome_novo:
                            novo_produto = Estoque(
                                nome_material=nome_novo, categoria=cat_nova,
                                quantidade=qtd_recebida, unidade_medida=und_nova,
                                custo_medio=preco_unitario_input,
                                data_validade=validade_lote, status_fispq=fispq_lote
                            )
                            session.add(novo_produto)
                            session.flush()
                            
                            nova_nota = EntradaNF(
                                produto_id=novo_produto.id, 
                                numero_nf=nf_numero,
                                fornecedor=fornecedor_input, 
                                quantidade_recebida=qtd_recebida,
                                preco_unitario=preco_unitario_input, 
                                data_recebimento=data_recebimento
                            
                            )
                            session.add(nova_nota)
                            session.commit()
                            st.success(f"Novo item MAT-{novo_produto.id:04d} inserido no catálogo com validações ativas!")
                            st.rerun()
                    else:
                        st.error("Preencha todos os campos do fluxo regulatório.")

        # 3. ABAS DE VISUALIZAÇÃO GERAIS
        aba_saldo, aba_historico_nf = st.tabs(["📋 Posição de Saldos e Controle Técnico", "🧾 Histórico Financeiro de NFs"])
        
        with aba_saldo:
            st.write("### Inventário Físico, Financeiro e de SGI")
            if todos_produtos:
                df_saldo = pd.DataFrame([{
                    "Código": f"MAT-{p.id:04d}",
                    "Descrição do Material": p.nome_material,
                    "Categoria": p.categoria,
                    "Qtd Saldo": f"{p.quantidade} {p.unidade_medida.split('(')[-1].replace(')','')}",
                    "Custo Médio": f"R$ {p.custo_medio:,.2f}",
                    "Imobilizado": f"R$ {(p.quantidade * p.custo_medio):,.2f}",
                    "Prazo Validade": p.data_validade.strftime('%d/%m/%Y') if p.data_validade else "Não Controlado",
                    "Status FISPQ/FDS": p.status_fispq if p.status_fispq else "N/A"
                } for p in todos_produtos])
                st.dataframe(df_saldo, use_container_width=True, hide_index=True)
                
                # Consumo / Baixa de estoque
                st.divider()
                st.write("#### 🔴 Registrar Saída de Material (Uso Interno)")
                lista_baixa = [f"MAT-{p.id:04d} | {p.nome_material}" for p in todos_produtos]
                prod_baixa_sel = st.selectbox("Selecione o item para consumo:", lista_baixa, key="baixa_sel")
                id_baixa = int(prod_baixa_sel.split("|")[0].split("-")[1])
                prod_baixa_bd = session.query(Estoque).filter_by(id=id_baixa).first()
                
                col_b1, col_b2 = st.columns([1, 2])
                with col_b1:
                    qtd_consumo = st.number_input("Quantidade Utilizada:", min_value=0.0, step=1.0)
                with col_b2:
                    st.write("")
                    st.write("")
                    if st.button("Confirmar Saída (Baixa pelo Custo Médio)", use_container_width=True):
                        if prod_baixa_bd and qtd_consumo > 0 and prod_baixa_bd.quantidade >= qtd_consumo:
                            prod_baixa_bd.quantidade -= qtd_consumo
                            session.commit()
                            st.success("Baixa realizada e estoque físico atualizado!")
                            st.rerun()
                        else:
                            st.error("Quantidade inválida ou saldo insuficiente.")
            else:
                st.info("Nenhum saldo ativo no almoxarifado.")
                
        with aba_historico_nf:
            st.write("### Livro de Registro de Entradas")
            if todas_nfs:
                mapa_nomes_produtos = {p.id: p.nome_material for p in todos_produtos}
                df_nf = pd.DataFrame([{
                    "Número NF-e": n.numero_nf,
                    "Fornecedor": n.fornecedor,
                    "Material": mapa_nomes_produtos.get(n.produto_id, "Desconhecido"),
                    "Qtd": n.quantidade_recebida,
                    "Preço Unitário": f"R$ {n.preco_unitario:,.2f}",
                    "Valor Total NF": f"R$ {(n.quantidade_recebida * n.preco_unitario):,.2f}",
                    "Data Entrada": n.data_recebimento.strftime('%d/%m/%Y')
                } for n in todas_nfs])
                st.dataframe(df_nf, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro documental processado.")

# ==========================================
    # PÁGINA 7: KANBAN DE TAREFAS (VERSÃO FINAL)
    # ==========================================
    elif menu == "📋 Kanban de Tarefas":
        st.title("📋 Kanban - Gestão Ágil de Tarefas e Prazos")
        
        # 1. FORMULÁRIO DE NOVA TAREFA
        with st.expander("➕ Criar Nova Tarefa", expanded=False):
            with st.form("form_nova_tarefa"):
                t_titulo = st.text_input("Título da Tarefa:")
                t_desc = st.text_area("Descrição ou Detalhes (Opcional):")
                
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    t_resp = st.text_input("Responsável pela Execução:")
                with col_t2:
                    t_prazo = st.date_input("Prazo Limite para Entrega:")
                
                if st.form_submit_button("Adicionar ao Quadro Kanban"):
                    if t_titulo and t_resp:
                        nova_tarefa = TarefaKanban(
                            titulo=t_titulo, descricao=t_desc, 
                            responsavel=t_resp, prazo=t_prazo
                        )
                        session.add(nova_tarefa)
                        session.commit()
                        st.success("Tarefa criada e enviada para a coluna 'A Fazer'!")
                        st.rerun()
                    else:
                        st.error("Preencha o Título e o Responsável.")

        st.divider()

        todas_tarefas = session.query(TarefaKanban).all()
        
        # 2. QUADRO KANBAN VISUAL (3 COLUNAS)
        col_todo, col_doing, col_done = st.columns(3)
        
        with col_todo:
            st.subheader("🔴 A Fazer")
            tarefas_todo = [t for t in todas_tarefas if t.status == "A Fazer"]
            for t in tarefas_todo:
                with st.container(border=True):
                    st.write(f"**{t.titulo}**")
                    if t.descricao: st.caption(t.descricao)
                    st.write(f"👤 {t.responsavel}")
                    st.write(f"📅 Prazo: {t.prazo.strftime('%d/%m/%Y')}")
                    
                    if t.prazo < hoje: st.error("⚠️ Atrasado!")
                    
                    if st.button("▶️ Iniciar", key=f"start_{t.id}", use_container_width=True):
                        t.status = "Em Andamento"
                        session.commit()
                        st.rerun()

        with col_doing:
            st.subheader("🟡 Em Andamento")
            tarefas_doing = [t for t in todas_tarefas if t.status == "Em Andamento"]
            for t in tarefas_doing:
                with st.container(border=True):
                    st.write(f"**{t.titulo}**")
                    if t.descricao: st.caption(t.descricao)
                    st.write(f"👤 {t.responsavel}")
                    st.write(f"📅 Prazo: {t.prazo.strftime('%d/%m/%Y')}")
                    
                    if t.prazo < hoje: st.error("⚠️ Atrasado!")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("⏪ Voltar", key=f"back_{t.id}", use_container_width=True):
                            t.status = "A Fazer"
                            session.commit()
                            st.rerun()
                    with col_btn2:
                        if st.button("✅ Concluir", key=f"done_{t.id}", type="primary", use_container_width=True):
                            t.status = "Concluída"
                            session.commit()
                            st.rerun()

        with col_done:
            st.subheader("🟢 Concluída")
            tarefas_done = [t for t in todas_tarefas if t.status == "Concluída"]
            for t in tarefas_done:
                with st.container(border=True):
                    st.write(f"~~**{t.titulo}**~~")
                    st.write(f"👤 {t.responsavel}")
                    st.success("Finalizada")
                    
                    col_done_btn1, col_done_btn2 = st.columns(2)
                    with col_done_btn1:
                        if st.button("⏪ Voltar", key=f"revert_{t.id}", use_container_width=True):
                            t.status = "Em Andamento"
                            session.commit()
                            st.rerun()
                    with col_done_btn2:
                        if st.button("🗄️ Arquivar", key=f"arq_{t.id}", use_container_width=True):
                            t.status = "Arquivada"
                            session.commit()
                            st.rerun()
                            
        st.divider()
        
        # 3. NOVA FUNCIONALIDADE: EDITAR PRAZO DE TAREFAS ATIVAS
        tarefas_ativas = [t for t in todas_tarefas if t.status in ["A Fazer", "Em Andamento"]]
        
        if tarefas_ativas:
            with st.expander("⚙️ Prorrogar / Ajustar Prazo de Tarefa Ativa", expanded=False):
                col_ed1, col_ed2 = st.columns([2, 1])
                
                with col_ed1:
                    # Monta a lista de seleção apenas com tarefas que ainda não foram concluídas
                    opcoes_ativas = [f"ID {t.id} | {t.titulo} (Responsável: {t.responsavel})" for t in tarefas_ativas]
                    tarefa_sel_texto = st.selectbox("Selecione a tarefa que ganhou flexibilidade de tempo:", opcoes_ativas, key="sel_ed_prazo")
                    id_ed = int(tarefa_sel_texto.split("|")[0].replace("ID ", "").strip())
                
                tarefa_ed_bd = session.query(TarefaKanban).filter_by(id=id_ed).first()
                
                if tarefa_ed_bd:
                    with col_ed2:
                        # Mostra um seletor de data pré-preenchido com o prazo atual da tarefa
                        novo_prazo = st.date_input("Definir Nova Data Limite:", value=tarefa_ed_bd.prazo, key=f"date_ed_{id_ed}")
                    
                    if st.button("💾 Salvar Alteração de Cronograma", use_container_width=True, key=f"btn_ed_{id_ed}"):
                        tarefa_ed_bd.prazo = novo_prazo
                        session.commit()
                        st.success(f"Sucesso! O prazo da tarefa '{tarefa_ed_bd.titulo}' foi reajustado para {novo_prazo.strftime('%d/%m/%Y')}.")
                        st.rerun()
        
        st.divider()
        
        # 4. HISTÓRICO DE TAREFAS ARQUIVADAS
        with st.expander("🗄️ Consultar Arquivo Morto (Histórico de Tarefas)", expanded=False):
            tarefas_arquivadas = [t for t in todas_tarefas if t.status == "Arquivada"]
            
            if tarefas_arquivadas:
                df_arq = pd.DataFrame([{
                    "ID": t.id,
                    "Título da Tarefa": t.titulo,
                    "Responsável": t.responsavel,
                    "Prazo Original": t.prazo.strftime('%d/%m/%Y'),
                    "Data Criação": t.data_criacao.strftime('%d/%m/%Y') if t.data_criacao else "N/D"
                } for t in tarefas_arquivadas])
                
                st.dataframe(df_arq, use_container_width=True, hide_index=True)
                
                st.write("#### 🔧 Gerenciar Arquivo")
                col_rest, col_del = st.columns([1, 2])
                with col_rest:
                    id_selecionado = st.selectbox("Selecione o ID da Tarefa para gerenciar:", [t.id for t in tarefas_arquivadas])
                
                if id_selecionado:
                    tarefa_restaurar = session.query(TarefaKanban).filter_by(id=id_selecionado).first()
                    with col_del:
                        st.write("")
                        st.write("")
                        col_acao1, col_acao2 = st.columns(2)
                        with col_acao1:
                            if st.button("⏪ Restaurar para 'Concluída'", use_container_width=True):
                                tarefa_restaurar.status = "Concluída"
                                session.commit()
                                st.success("Tarefa restaurada para o quadro Kanban!")
                                st.rerun()
                        with col_acao2:
                            if st.checkbox("Confirmar exclusão permanente"):
                                if st.button("🗑️ Deletar Definitivamente", type="primary", use_container_width=True):
                                    session.delete(tarefa_restaurar)
                                    session.commit()
                                    st.success("Tarefa excluída do banco de dados!")
                                    st.rerun()
            else:
                st.info("O arquivo morto está vazio. Nenhuma tarefa foi arquivada no momento.")


session.close()