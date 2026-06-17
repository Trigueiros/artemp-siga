import streamlit as st
import pandas as pd
import altair as alt
import hashlib
import json 
import requests # <-- NOVA BIBLIOTECA AQUI
from datetime import date
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
# Importamos a nova tabela NaoConformidade do banco de dados
from banco_dados import Residuo, Licenca, Usuario, NaoConformidade, Estoque, EntradaNF, TarefaKanban, OrdemProducao, ConsumoOP, ProdutoAcabado, Venda

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


# =====================================================================
# GATILHO DE INICIALIZAÇÃO BLINDADO (Cria ou Força a Atualização)
# =====================================================================
admin_existe = session.query(Usuario).filter_by(username="ss.strigueiros").first()
senha_padrao = criptografar_senha("S@muel0099") 

if not admin_existe:
    # Se não existir, cria do zero
    primeiro_admin = Usuario(
        username="ss.strigueiros",
        senha_hash=senha_padrao,
        nome_completo="Samuel de Souza Trigueiros",
        cargo="Super Admin",
        modulos_acesso="TODOS"
    )
    session.add(primeiro_admin)
    session.commit()
else:
    # Se já existir (travado), esmaga a senha antiga e força a nova e os acessos totais
    admin_existe.senha_hash = senha_padrao
    admin_existe.cargo = "Super Admin"
    admin_existe.modulos_acesso = "TODOS"
    session.commit()
# =====================================================================

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
                # 1. Limpeza rigorosa: remove espaços no início/fim e força minúsculas
                usuario_limpo = user_input.strip().lower()
                senha_limpa = senha_input.strip()
                
                # 2. Criptografa a senha já limpa
                hash_busca = criptografar_senha(senha_limpa)
                
                # 3. Faz a busca no banco usando os dados tratados
                usuario_encontrado = session.query(Usuario).filter_by(username=usuario_limpo, senha_hash=hash_busca).first()
                
                if usuario_encontrado:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = usuario_encontrado.nome_completo
                    st.session_state.cargo_atual = usuario_encontrado.cargo
                    st.session_state.modulos_acesso = usuario_encontrado.modulos_acesso
                    
                    st.success("Acesso autorizado! Bem-vindo.")
                    st.rerun()
                else:
                    # Mensagem de erro mais descritiva para depuração
                    st.error(f"Acesso negado para o usuário '{usuario_limpo}'. Verifique as credenciais.")
                    
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
    # --- NOVO MENU DINÂMICO ---
    TODOS_MODULOS = [
        "📊 Dashboard", 
        "📝 Lançamentos", 
        "📅 Licenças", 
        "📂 Gestão Documental", 
        "⚠️ Não Conformidades",
        "📦 Almoxarifado / Estoque",
        "🏭 Produção (MRP)",
        "💰 Comercial / Vendas", 
        "📋 Kanban de Tarefas", 
        "⚙️ Painel Admin"
    ]

    # Verifica o que o usuário pode ver baseado na memória do login
    if st.session_state.cargo_atual == "Super Admin" or st.session_state.modulos_acesso == "TODOS":
        modulos_permitidos = TODOS_MODULOS
    else:
        # Pega o texto do banco (ex: "📊 Dashboard,🏭 Produção (MRP)") e quebra em uma lista
        modulos_permitidos = st.session_state.modulos_acesso.split(",")
        
        # Trava de segurança caso a lista venha vazia
        if not modulos_permitidos or modulos_permitidos == [""]:
            modulos_permitidos = ["📊 Dashboard"]

    menu = st.sidebar.radio("Navegação:", modulos_permitidos)

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
                                nome_material=nome_novo, 
                                categoria=cat_nova,
                                quantidade=qtd_recebida, 
                                unidade_medida=und_nova,
                                custo_medio=preco_unitario_input,
                                data_validade=validade_lote, 
                                status_fispq=fispq_lote,
                                fornecedor=fornecedor_input,  # <-- O VILÃO RESOLVIDO AQUI!
                                nota_fiscal=nf_numero         # <-- Aproveitando a carona
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

# ==========================================
    # PÁGINA 8: PRODUÇÃO (MRP) E PRODUTOS ACABADOS
    # ==========================================
    elif menu == "🏭 Produção (MRP)":
        st.title("🏭 Controle de Produção e Produtos Acabados")
        
        tab_op, tab_estoque_final = st.tabs(["📋 Gestão de Ordens de Produção", "📦 Inventário de Produtos Acabados"])
        
        # --- ABA 1: ORDENS DE PRODUÇÃO ---
        with tab_op:
            # 1. Abertura de OP
            with st.expander("➕ Abrir Nova Ordem de Produção (OP)", expanded=False):
                
                # Lógica de rastreio automático: busca a última OP registrada para gerar a próxima
                ultima_op = session.query(OrdemProducao).order_by(OrdemProducao.id.desc()).first()
                proximo_numero = ultima_op.id + 1 if ultima_op else 1
                codigo_gerado = f"OP-{proximo_numero:03d}"
                
                with st.form("form_nova_op"):
                    col_op1, col_op2 = st.columns(2)
                    with col_op1:
                        # Campo bloqueado (disabled=True) para evitar erro humano
                        st.text_input("Código da OP (Gerado Automaticamente):", value=codigo_gerado, disabled=True)
                        nome_prod = st.text_input("Nome do Produto a ser Fabricado:")
                    with col_op2:
                        qtd_esperada = st.number_input("Quantidade Esperada (Unidades/Litros):", min_value=0.1, format="%.2f")
                    
                    if st.form_submit_button("Abrir OP"):
                        if nome_prod:
                            # O sistema salva usando a variável codigo_gerado que ele mesmo criou
                            nova_op = OrdemProducao(codigo_op=codigo_gerado, nome_produto=nome_prod, quantidade_esperada=qtd_esperada)
                            session.add(nova_op)
                            session.commit()
                            st.success(f"Ordem de Produção {codigo_gerado} aberta com sucesso!")
                            st.rerun()
                        else:
                            st.error("Preencha o nome do produto.")
            
            st.divider()
            
            
           # 2. Requisição de Materiais e Apontamento
            ops_abertas = session.query(OrdemProducao).filter_by(status="Aberta").all()
            if ops_abertas:
                st.subheader("⚙️ Requisição de Materiais para Produção")
                
                with st.container(border=True):
                    # Aqui nascem as colunas que estavam faltando!
                    col_req1, col_req2 = st.columns([1, 2])
                    
                    with col_req1:
                        op_selecionada = st.selectbox("Selecione a OP Aberta:", [f"{op.id} | {op.codigo_op} - {op.nome_produto}" for op in ops_abertas])
                        id_op = int(op_selecionada.split(" | ")[0])
                        op_atual = session.query(OrdemProducao).filter_by(id=id_op).first()
                    
                    with col_req2:
                        todos_insumos = session.query(Estoque).all()
                        insumo_sel = st.selectbox(
                            "Selecione a Matéria-Prima / Insumo (Almoxarifado):", 
                            [f"{i.id} | {i.nome_material} (Saldo: {i.quantidade} {i.unidade_medida})" for i in todos_insumos if i.quantidade > 0]
                        )
                        id_insumo = int(insumo_sel.split(" | ")[0])
                        insumo_atual = session.query(Estoque).filter_by(id=id_insumo).first()
                    
                    # Alinhamento recuado para fora das colunas
                    qtd_requisitar = st.number_input(f"Quantidade a transferir para a OP ({insumo_atual.unidade_medida}):", min_value=0.01, max_value=float(insumo_atual.quantidade), format="%.2f")
                    
                    if st.button("🔽 Baixar Insumo para Produção", type="primary", use_container_width=True):
                        # Calcula o custo da matéria prima baseada no custo médio atual do almoxarifado
                        custo_consumo = qtd_requisitar * insumo_atual.custo_medio
                        
                        # 1. Dá baixa física no Almoxarifado Geral
                        insumo_atual.quantidade -= qtd_requisitar
                        
                        # 2. Registra o consumo rastreável na OP
                        novo_consumo = ConsumoOP(
                            op_id=op_atual.id, 
                            material_id=insumo_atual.id, 
                            quantidade_consumida=qtd_requisitar, 
                            custo_alocado=custo_consumo
                        )
                        session.add(novo_consumo)
                        
                        # 3. Atualiza o custo financeiro total da OP
                        op_atual.custo_total += custo_consumo
                        
                        session.commit()
                        st.success(f"Insumo baixado! R$ {custo_consumo:.2f} agregados ao custo da OP.")
                        st.rerun()

                st.divider()
            st.divider()
                
                # 3. Fechamento da OP
            st.subheader("✅ Encerramento de Ordem de Produção")
                
            opcoes_encerramento = [f"{op.id} | {op.codigo_op} - {op.nome_produto} (Custo Atual: R$ {op.custo_total:.2f})" for op in ops_abertas]
            op_encerrar_str = st.selectbox("Selecione a OP para Finalizar e gerar Produto Acabado:", opcoes_encerramento)
                
                # O ESCUDO: Só executa se o Streamlit realmente carregou um texto na caixa de seleção
            if op_encerrar_str:
                    id_op_encerrar = int(op_encerrar_str.split(" | ")[0])
                    op_encerrar = session.query(OrdemProducao).filter_by(id=id_op_encerrar).first()
                    
                    qtd_produzida_real = st.number_input("Quantidade Real Produzida:", value=float(op_encerrar.quantidade_esperada), format="%.2f")
                    
                    if st.button("🔒 Finalizar OP e Transferir para Estoque Acabado", use_container_width=True):
                        # Calcula o Custo Unitário Final do produto gerado
                        custo_unit_final = op_encerrar.custo_total / qtd_produzida_real if qtd_produzida_real > 0 else 0
                        
                        # Procura se o Produto Acabado já existe no estoque isolado
                        produto_existente = session.query(ProdutoAcabado).filter_by(descricao=op_encerrar.nome_produto).first()
                        
                        if produto_existente:
                            # Se já existe, atualiza a quantidade e faz o custo médio ponderado
                            valor_total_antigo = produto_existente.quantidade * produto_existente.custo_unitario
                            novo_valor_total = valor_total_antigo + op_encerrar.custo_total
                            produto_existente.quantidade += qtd_produzida_real
                            produto_existente.custo_unitario = novo_valor_total / produto_existente.quantidade
                            produto_existente.valor_total = novo_valor_total
                            produto_existente.data_ultima_entrada = date.today()
                        else:
                            # Se não existe, cria um registro novo no inventário de acabados
                            novo_produto = ProdutoAcabado(
                                codigo=op_encerrar.codigo_op, 
                                descricao=op_encerrar.nome_produto, 
                                quantidade=qtd_produzida_real, 
                                custo_unitario=custo_unit_final,
                                valor_total=op_encerrar.custo_total
                            )
                            session.add(novo_produto)
                        
                        # Muda o status da OP para não aparecer mais
                        op_encerrar.status = "Concluída"
                        op_encerrar.data_conclusao = date.today()
                        
                        session.commit()
                        st.success(f"OP Finalizada! O item '{op_encerrar.nome_produto}' já está no Inventário de Produtos Acabados.")
                        st.rerun()
            else:
                st.info("Não há Ordens de Produção abertas no momento.")

        # --- ABA 2: INVENTÁRIO DE PRODUTOS ACABADOS ---
        with tab_estoque_final:
            st.subheader("📦 Galpão de Produtos Acabados (Finalizados)")
            
            produtos_acabados = session.query(ProdutoAcabado).all()
            
            if produtos_acabados:
                capital_final_imobilizado = sum([p.valor_total for p in produtos_acabados])
                
                st.metric("Capital Imobilizado (Produtos Prontos para Venda/Uso)", f"R$ {capital_final_imobilizado:.2f}")
                
                df_acabados = pd.DataFrame([{
                    "Código (Última OP)": p.codigo,
                    "Descrição do Produto Final": p.descricao,
                    "Saldo Físico": f"{p.quantidade:.2f}",
                    "Custo de Produção (Unit)": f"R$ {p.custo_unitario:.2f}",
                    "Valor Imobilizado": f"R$ {p.valor_total:.2f}",
                    "Última Produção": p.data_ultima_entrada.strftime('%d/%m/%Y')
                } for p in produtos_acabados])
                
                st.dataframe(df_acabados, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum produto acabado consta no inventário separado.")

# ==========================================
    # PÁGINA 9: COMERCIAL E FATURAMENTO
    # ==========================================
    elif menu == "💰 Comercial / Vendas":
        st.title("💰 Gestão Comercial e Faturamento")
        
        # Adicionada a nova aba fiscal
        tab_venda, tab_relatorio, tab_fiscal = st.tabs(["🛒 Registrar Novo Pedido", "📈 Relatório de Faturamento", "🧾 Painel Fiscal (NF-e/NFC-e)"])
        
        # --- ABA 1: REGISTRAR VENDA ---
        with tab_venda:
            produtos_disponiveis = session.query(ProdutoAcabado).filter(ProdutoAcabado.quantidade > 0).all()
            
            if produtos_disponiveis:
                with st.container(border=True):
                    st.subheader("Emitir Pedido de Venda")
                    
                    col_v1, col_v2 = st.columns([2, 1])
                    
                    with col_v1:
                        produto_sel = st.selectbox(
                            "Selecione o Produto Acabado:", 
                            [f"{p.id} | {p.codigo} - {p.descricao} (Estoque: {p.quantidade:.2f} unid. / Custo Unit: R$ {p.custo_unitario:.2f})" for p in produtos_disponiveis]
                        )
                        id_produto = int(produto_sel.split(" | ")[0])
                        produto_atual = session.query(ProdutoAcabado).filter_by(id=id_produto).first()
                        
                        cliente_input = st.text_input("Nome do Cliente / Empresa:")
                    
                    with col_v2:
                        qtd_venda = st.number_input("Quantidade a Vender:", min_value=0.01, max_value=float(produto_atual.quantidade), format="%.2f")
                        preco_venda = st.number_input("Preço de Venda (Por Unidade):", min_value=0.01, value=float(produto_atual.custo_unitario * 1.5), format="%.2f")
                    
                    if st.button("✅ Confirmar Venda e Baixar Estoque", type="primary", use_container_width=True):
                        if cliente_input:
                            receita_total = qtd_venda * preco_venda
                            custo_total_venda = qtd_venda * produto_atual.custo_unitario
                            
                            produto_atual.quantidade -= qtd_venda
                            produto_atual.valor_total = produto_atual.quantidade * produto_atual.custo_unitario
                            
                            nova_venda = Venda(
                                produto_id=produto_atual.id,
                                nome_produto=produto_atual.descricao,
                                cliente=cliente_input,
                                quantidade_vendida=qtd_venda,
                                preco_unitario_venda=preco_venda,
                                valor_total_venda=receita_total,
                                custo_total_produto=custo_total_venda,
                                status_fiscal="Pendente" # Nasce pendente de emissão
                            )
                            session.add(nova_venda)
                            session.commit()
                            
                            st.success(f"Venda registrada! O pedido foi enviado para o Painel Fiscal para emissão da nota.")
                            st.rerun()
                        else:
                            st.error("Por favor, preencha o nome do cliente.")
            else:
                st.info("Não há Produtos Acabados em estoque para venda.")

        # --- ABA 2: RELATÓRIO DE FATURAMENTO ---
        with tab_relatorio:
            todas_vendas = session.query(Venda).order_by(Venda.data_venda.desc()).all()
            
            if todas_vendas:
                faturamento_total = sum([v.valor_total_venda for v in todas_vendas])
                custo_total_cmv = sum([v.custo_total_produto for v in todas_vendas])
                lucro_total = faturamento_total - custo_total_cmv
                
                col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                col_kpi1.metric("Faturamento", f"R$ {faturamento_total:.2f}")
                col_kpi2.metric("CMV", f"R$ {custo_total_cmv:.2f}", delta="Saída", delta_color="inverse")
                col_kpi3.metric("Lucro Bruto", f"R$ {lucro_total:.2f}")
                
                st.divider()
                
                df_vendas = pd.DataFrame([{
                    "ID": v.id,
                    "Data": v.data_venda.strftime('%d/%m/%Y'),
                    "Cliente": v.cliente,
                    "Produto": v.nome_produto,
                    "Total": f"R$ {v.valor_total_venda:.2f}",
                    "Status Fiscal": v.status_fiscal,
                    "Nº NF": v.numero_nf if v.numero_nf else "-"
                } for v in todas_vendas])
                
                st.dataframe(df_vendas, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma venda registrada até o momento.")
                
        # --- ABA 3: PAINEL FISCAL (MÓDULO SEFAZ / API) ---
        with tab_fiscal:
            st.subheader("📡 Central de Integração com SEFAZ")
            
            vendas_pendentes = session.query(Venda).filter_by(status_fiscal="Pendente").all()
            
            if vendas_pendentes:
                st.warning(f"Existem {len(vendas_pendentes)} vendas aguardando emissão de nota fiscal.")
                
                venda_sel_str = st.selectbox(
                    "Selecione o pedido para faturar:", 
                    [f"{v.id} | Cliente: {v.cliente} - {v.nome_produto} (R$ {v.valor_total_venda:.2f})" for v in vendas_pendentes]
                )
                
                id_venda_fiscal = int(venda_sel_str.split(" | ")[0])
                venda_fiscal = session.query(Venda).filter_by(id=id_venda_fiscal).first()
                
                tipo_nota = st.radio("Selecione o modelo da nota:", ["NFC-e (Consumidor Final)", "NF-e (Produto/Atacado)"], horizontal=True)
                
                st.divider()
                st.write("**Simulação do Payload (JSON que será enviado para a API):**")
                
                # Este é o esqueleto exato da estrutura que a API vai exigir na próxima etapa
                payload_mock = {
                    "natureza_operacao": "Venda de mercadoria",
                    "data_emissao": date.today().isoformat(),
                    "consumidor_final": 1 if "NFC-e" in tipo_nota else 0,
                    "itens": [
                        {
                            "numero_item": 1,
                            "descricao": venda_fiscal.nome_produto,
                            "cfop": "5102", # Código padrão para revenda/venda estadual
                            "unidade_comercial": "UN",
                            "quantidade_comercial": venda_fiscal.quantidade_vendida,
                            "valor_unitario_comercial": venda_fiscal.preco_unitario_venda,
                            "valor_bruto": venda_fiscal.valor_total_venda,
                        }
                    ],
                    "pagamentos": [
                        {
                            "forma_pagamento": "Dinheiro/Pix",
                            "valor_pagamento": venda_fiscal.valor_total_venda
                        }
                    ]
                }
                
                st.json(payload_mock)
                
                if st.button("🚀 Enviar para SEFAZ-BA (API Focus NFe)", type="primary"):
                    try:
                        # 1. Pega a senha silenciosamente do seu cofre
                        token = st.secrets["focus_nfe"]["token_sandbox"]
                        
                        # 2. Define para qual endereço o pacote vai (Endpoint de NFC-e)
                        url_api = "https://api.focusnfe.com.br/v2/nfce"
                        
                        # A Focus NFe usa o token como usuário e deixa a senha em branco
                        autenticacao = (token, "") 
                        
                        # 3. Dispara a requisição para a internet
                        with st.spinner("Conectando aos servidores do Governo da Bahia..."):
                            # Usamos um timeout para o sistema não travar se a SEFAZ estiver fora do ar
                            resposta = requests.post(url_api, json=payload_mock, auth=autenticacao, timeout=15)
                        
                        # 4. O Cérebro: Interpreta a resposta da SEFAZ
                        if resposta.status_code in [200, 201, 202]:
                            # Sucesso! A nota foi gerada ou está em processamento
                            dados_retorno = resposta.json()
                            
                            # Puxa o número oficial ou cria um rastreio provisório
                            numero_oficial = dados_retorno.get("numero", f"API-{venda_fiscal.id}")
                            
                            # Grava no seu banco de dados
                            venda_fiscal.status_fiscal = "Emitida"
                            venda_fiscal.numero_nf = numero_oficial
                            session.commit()
                            
                            st.success(f"✅ Sucesso! NFC-e {numero_oficial} autorizada.")
                            st.rerun()
                        else:
                            # Rejeição da SEFAZ (ex: NCM do chocolate incorreto, CNPJ inválido)
                            # O sistema tenta ler a mensagem de erro oficial para você saber o que corrigir
                            try:
                                erro_msg = resposta.json().get("mensagem", resposta.text)
                            except:
                                erro_msg = resposta.text
                                
                            st.error(f"❌ Rejeição Fiscal (Código {resposta.status_code}): {erro_msg}")
                            
                    except FileNotFoundError:
                         st.error("⚠️ Arquivo secrets.toml não encontrado na pasta .streamlit!")
                    except Exception as e:
                        st.error(f"⚠️ Erro de conexão de rede com a API: {e}")

# 🔹 ADICIONA ESTE BLOCO NO FINAL DO TEU APP.PY:
    elif menu == "⚙️ Painel Admin":
        if st.session_state.cargo_atual != "Super Admin":
            st.error("🚫 Acesso Negado. Apenas o Super Administrador pode aceder a este módulo.")
        else:
            st.title("⚙️ Administração do Sistema e Utilizadores")
            st.write("Cria novos utilizadores e define quais os módulos do ERP que cada um pode aceder.")
            
            with st.expander("👤 Cadastrar Novo Utilizador / Funcionário", expanded=True):
                with st.form("form_novo_usuario"):
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        nome_func = st.text_input("Nome Completo:")
                        login_func = st.text_input("Utilizador (Login):")
                    with col_u2:
                        senha_func = st.text_input("Senha:", type="password")
                        cargo_func = st.text_input("Cargo (Ex: Operador de Produção, Vendedor):")
                    
                    st.divider()
                    st.write("**Liberação de Módulos (Selecione o que o funcionário pode aceder):**")
                    
                    modulos_selecionados = []
                    col_cb1, col_cb2, col_cb3 = st.columns(3)
                    
                    for idx, mod in enumerate(TODOS_MODULOS[:-1]):
                        if idx % 3 == 0:
                            with col_cb1:
                                if st.checkbox(mod, key=f"cb_{idx}"): modulos_selecionados.append(mod)
                        elif idx % 3 == 1:
                            with col_cb2:
                                if st.checkbox(mod, key=f"cb_{idx}"): modulos_selecionados.append(mod)
                        else:
                            with col_cb3:
                                if st.checkbox(mod, key=f"cb_{idx}"): modulos_selecionados.append(mod)
                                
                    if st.form_submit_button("Salvar Utilizador", type="primary"):
                        if login_func and senha_func:
                            hash_senha = criptografar_senha(senha_func)
                            string_modulos = ",".join(modulos_selecionados)
                            novo_usr = Usuario(
                                username=login_func,
                                senha_hash=hash_senha, 
                                nome_completo=nome_func,
                                cargo=cargo_func,
                                modulos_acesso=string_modulos
                            )
                            session.add(novo_usr)
                            session.commit()
                            st.success(f"Funcionário '{nome_func}' cadastrado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Preencha o utilizador e a senha.")

# --- NOVO BLOCO: EDITAR E REVOGAR ACESSOS ---
            with st.expander("✏️ Editar ou Revogar Permissões de Usuários Existentes", expanded=False):
                # Busca todos os usuários, exceto o Super Admin (para evitar que você tranque a si mesmo de fora)
                usuarios_existentes = session.query(Usuario).filter(Usuario.cargo != "Super Admin").all()
                
                if usuarios_existentes:
                    usuario_selecionado = st.selectbox(
                        "Selecione o Funcionário para alterar acessos:", 
                        [f"{u.id} | {u.nome_completo} ({u.cargo})" for u in usuarios_existentes]
                    )
                    
                    # Puxa o ID do usuário selecionado no menu suspenso
                    id_edit = int(usuario_selecionado.split(" | ")[0])
                    usr_edit = session.query(Usuario).filter_by(id=id_edit).first()
                    
                    st.write(f"**Editando acessos de:** {usr_edit.nome_completo} ({usr_edit.username})")
                    
                    # Descobre quais módulos ele já tem hoje para deixar as caixinhas pré-marcadas
                    modulos_atuais = usr_edit.modulos_acesso.split(",") if usr_edit.modulos_acesso else []
                    
                    with st.form("form_editar_permissoes"):
                        modulos_atualizados = []
                        col_e1, col_e2, col_e3 = st.columns(3)
                        
                        for idx, mod in enumerate(TODOS_MODULOS[:-1]):
                            # A caixinha já aparece marcada se o módulo estiver no banco de dados dele
                            is_checked = mod in modulos_atuais
                            
                            if idx % 3 == 0:
                                with col_e1:
                                    if st.checkbox(mod, value=is_checked, key=f"edit_cb_{idx}"): modulos_atualizados.append(mod)
                            elif idx % 3 == 1:
                                with col_e2:
                                    if st.checkbox(mod, value=is_checked, key=f"edit_cb_{idx}"): modulos_atualizados.append(mod)
                            else:
                                with col_e3:
                                    if st.checkbox(mod, value=is_checked, key=f"edit_cb_{idx}"): modulos_atualizados.append(mod)
                                    
                        if st.form_submit_button("🔄 Atualizar Permissões", type="primary"):
                            # Transforma a nova lista de marcações em texto e salva por cima da antiga
                            nova_string_modulos = ",".join(modulos_atualizados)
                            usr_edit.modulos_acesso = nova_string_modulos
                            session.commit()
                            
                            st.success(f"Permissões de {usr_edit.nome_completo} atualizadas com sucesso!")
                            st.rerun()
                else:
                    st.info("Nenhum usuário comum cadastrado ainda para ser editado.")


session.close()