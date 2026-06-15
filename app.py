import streamlit as st
import pandas as pd
import altair as alt
import hashlib
import json
from datetime import date
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
# Importamos a nova tabela NaoConformidade do banco de dados
from banco_dados import Residuo, Licenca, Usuario, NaoConformidade, Estoque, EntradaNF 

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
    menu = st.sidebar.radio("Navegação:", ["📊 Dashboard", "📝 Lançamentos", "📅 Licenças", "📂 Gestão Documental", "⚠️ Não Conformidades", "📦 Almoxarifado / Estoque"])

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
    # PÁGINA 5: NOVA - NÃO CONFORMIDADES (SGI)
    # ==========================================
    elif menu == "⚠️ Não Conformidades":
        st.title("⚠️ Tratamento de Não Conformidades e Plano de Ação")
        
        # 1. FORMULÁRIO DE CADASTRO DE NC
        with st.expander("➕ Registrar Nova Não Conformidade (RNC)", expanded=False):
            with st.form("form_nova_nc"):
                st.subheader("Evidência e Descrição da Ocorrência")
                desc_input = st.text_area("Descrição Ocorrência / Não Conformidade encontrada:")
                
                col_nc1, col_nc2 = st.columns(2)
                with col_nc1:
                    acao_input = st.text_area("Ação Proposta (O que será feito para mitigar/resolver?):")
                    responsavel_input = st.text_input("Colaborador Responsável pela Execução:")
                with col_nc2:
                    data_detecao = st.date_input("Data de Identificação", date.today())
                    prazo_input = st.date_input("Cronograma - Prazo Limite para Conclusão da Ação:", date.today())
                
                btn_salvar_nc = st.form_submit_button("Emitir Relatório de Não Conformidade")
                
                if btn_salvar_nc:
                    if desc_input and acao_input and responsavel_input:
                        nova_nc = NaoConformidade(
                            descricao=desc_input, acao_proposta=acao_input,
                            responsavel=responsavel_input, data_registro=data_detecao,
                            prazo_limite=prazo_input, status="Aberta"
                        )
                        session.add(nova_nc)
                        session.commit()
                        st.success("Não Conformidade registrada no plano de ação com sucesso!")
                        st.rerun()
                    else:
                        st.error("Por favor, preencha todos os campos do plano de ação.")

        st.write("### 📊 Quadro de Planos de Ação e Cronogramas")
        
        if todas_ncs:
            # Monta tabela visual das NCs com a máscara de "Código de ERP"
            dados_nc_df = pd.DataFrame([{
                "Código RNC": f"RNC-{n.id:05d}", # Formata o ID para ter 5 dígitos (ex: RNC-00001)
                "Descrição do Desvio": n.descricao,
                "Plano de Ação Corretiva": n.acao_proposta,
                "Responsável": n.responsavel,
                "Abertura": n.data_registro.strftime('%d/%m/%Y'),
                "Prazo Final": n.prazo_limite.strftime('%d/%m/%Y'),
                "Status Atual": n.status
            } for n in todas_ncs])
            
            st.dataframe(dados_nc_df, use_container_width=True, hide_index=True)
            st.divider()
            
            # 2. BARRA DE PESQUISA INTELIGENTE
            st.write("#### 🔍 Buscar e Atualizar RNC")
            st.info("💡 Você pode digitar apenas o número (Ex: 1) ou o código completo (Ex: RNC-00001)")
            
            busca_rnc = st.text_input("🔎 Digite o Código da RNC para localizar:")
            
            if busca_rnc:
                # O Python extrai apenas os números da frase digitada (ignora letras e traços)
                id_str = "".join(filter(str.isdigit, busca_rnc))
                
                if id_str:
                    id_busca = int(id_str)
                    nc_alterar = session.query(NaoConformidade).filter_by(id=id_busca).first()
                    
                    if nc_alterar:
                        st.success(f"✅ Ocorrência Encontrada: **RNC-{nc_alterar.id:05d}**")
                        
                        # Coloca o formulário de atualização dentro de um quadro bonitão
                        with st.container(border=True):
                            st.write(f"**Problema Identificado:** {nc_alterar.descricao}")
                            st.write(f"**Ação Definida:** {nc_alterar.acao_proposta}")
                            
                            status_opcoes = ["Aberta", "Em Andamento", "Tratada", "Concluída"]
                            try: idx_status_nc = status_opcoes.index(nc_alterar.status)
                            except: idx_status_nc = 0
                            
                            novo_status_nc = st.selectbox("Alterar Status da Ação:", status_opcoes, index=idx_status_nc)
                            novo_prazo_nc = st.date_input("Ajustar Prazo Limite:", value=nc_alterar.prazo_limite)
                            
                            col_nc_btn1, col_nc_btn2 = st.columns(2)
                            with col_nc_btn1:
                                if st.button("🔄 Salvar Atualização", use_container_width=True):
                                    nc_alterar.status = novo_status_nc
                                    nc_alterar.prazo_limite = novo_prazo_nc
                                    session.commit()
                                    st.success(f"RNC-{nc_alterar.id:05d} atualizada para '{novo_status_nc}'!")
                                    st.rerun()
                            with col_nc_btn2:
                                if st.checkbox("Confirmar exclusão desta ocorrência"):
                                    if st.button("🗑️ Deletar Registro", type="primary", use_container_width=True):
                                        session.delete(nc_alterar)
                                        session.commit()
                                        st.success("Registro removido!")
                                        st.rerun()
                    else:
                        st.error(f"❌ Nenhuma RNC encontrada com o número {id_busca}. Verifique a tabela acima.")
                else:
                    st.warning("⚠️ Por favor, digite um número válido para realizar a busca.")
        else:
            st.info("Nenhuma Não Conformidade registrada no momento. O SGI está 100% em conformidade!")

# ==========================================
    # PÁGINA 6: ALMOXARIFADO / ESTOQUE (FISCAL)
    # ==========================================
    elif menu == "📦 Almoxarifado / Estoque":
        st.title("📦 Gestão de Almoxarifado e Recebimento de Notas Fiscais")
        
        # Busca os dados atuais do banco
        todos_produtos = session.query(Estoque).all()
        todas_nfs = session.query(EntradaNF).all()
        
        # 1. FORMULÁRIO DE RECEBIMENTO DE NOTA FISCAL
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
                    qtd_recebida = st.number_input("Quantidade Recebida nesta NF:", min_value=0.0, step=1.0)
                    data_recebimento = st.date_input("Data de Entrada Física:", date.today())
                
                with col_nf2:
                    st.subheader("Vínculo do Produto")
                    if tipo_entrada == "Sim, produto já cadastrado":
                        if todos_produtos:
                            # Cria uma lista de seleção com os produtos que já existem
                            opcoes_produtos = [f"MAT-{p.id:04d} | {p.nome_material}" for p in todos_produtos]
                            produto_selecionado = st.selectbox("Selecione o Produto Destino:", opcoes_produtos)
                            # Deixa os campos de cadastro novos ocultos/vazios
                            nome_novo, cat_nova, und_nova = "", "", ""
                        else:
                            st.warning("Nenhum produto cadastrado ainda. Mude para a opção 'Produto Novo'.")
                            produto_selecionado = None
                    else:
                        # Se for produto novo, abre os campos para criar o registro fixo dele
                        nome_novo = st.text_input("Nome do Novo Material / Produto:")
                        cat_nova = st.selectbox("Categoria:", ["EPI (Equip. Proteção)", "Insumos Químicos", "Ferramentas", "Peças de Reposição", "Outros"])
                        und_nova = st.selectbox("Unidade de Medida:", ["Unidade (un)", "Quilograma (kg)", "Litro (L)", "Caixa (cx)"])
                        produto_selecionado = None
                
                btn_processar_nf = st.form_submit_button("⚙️ Processar Entrada Fiscal")
                
                if btn_processar_nf:
                    if nf_numero and fornecedor_input and qtd_recebida > 0:
                        
                        # CENÁRIO A: O produto já existe. Apenas atualizamos o saldo e registramos a NF.
                        if tipo_entrada == "Sim, produto já cadastrado" and produto_selecionado:
                            id_produto = int(produto_selecionado.split("|")[0].split("-")[1])
                            produto_bd = session.query(Estoque).filter_by(id=id_produto).first()
                            
                            if produto_bd:
                                # Soma a quantidade da nova NF ao saldo fixo existente
                                produto_bd.quantidade += qtd_recebida
                                
                                # Salva o histórico da Nota Fiscal vinculada a ele
                                nova_nota = EntradaNF(
                                    produto_id=produto_bd.id, numero_nf=nf_numero,
                                    fornecedor=fornecedor_input, quantidade_recebida=qtd_recebida,
                                    data_recebimento=data_recebimento
                                )
                                session.add(nova_nota)
                                session.commit()
                                st.success(f"Nota Fiscal {nf_numero} processada! Saldo do item {produto_bd.nome_material} atualizado.")
                                st.rerun()
                        
                        # CENÁRIO B: O produto é novo. Criamos o registro fixo no estoque e atrelamos a NF.
                        elif tipo_entrada == "Não, é um produto novo" and nome_novo:
                            # Cria o registro mestre do produto com o saldo inicial da NF
                            novo_produto = Estoque(
                                nome_material=nome_novo, categoria=cat_nova,
                                quantidade=qtd_recebida, unidade_medida=und_nova
                            )
                            session.add(novo_produto)
                            session.flush() # Faz o banco gerar o ID do produto antes do commit final
                            
                            # Cria o registro da NF apontando para o ID recém-criado
                            nova_nota = EntradaNF(
                                produto_id=novo_produto.id, numero_nf=nf_numero,
                                fornecedor=fornecedor_input, quantidade_recebida=qtd_recebida,
                                data_recebimento=data_recebimento
                              )
                            session.add(nova_nota)
                            session.commit()
                            st.success(f"Novo produto cadastrado (MAT-{novo_produto.id:04d}) e Nota Fiscal {nf_numero} vinculada!")
                            st.rerun()
                        else:
                            st.error("Preencha as informações do novo produto.")
                    else:
                        st.error("Por favor, preencha o número da NF, fornecedor e insira uma quantidade válida.")

        # Visões de Dados em Abas para organizar o ERP
        aba_saldo, aba_historico_nf = st.tabs(["📋 Posição Atual do Estoque (Saldos)", "🧾 Livro de Registro de Notas Fiscais"])
        
        with aba_saldo:
            st.write("### Posição Física de Almoxarifado")
            if todos_produtos:
                df_saldo = pd.DataFrame([{
                    "Código Código": f"MAT-{p.id:04d}",
                    "Descrição do Material": p.nome_material,
                    "Categoria": p.categoria,
                    "Saldo em Prateleira": f"{p.quantidade} {p.unidade_medida.split('(')[-1].replace(')','')}"
                } for p in todos_produtos])
                st.dataframe(df_saldo, use_container_width=True, hide_index=True)
                
                # Controle rápido de Saída/Consumo diário (Mantido para baixar o estoque quando usado)
                st.divider()
                st.write("#### 🔴 Registrar Consumo / Baixa de Material Interno")
                lista_baixa = [f"MAT-{p.id:04d} | {p.nome_material}" for p in todos_produtos]
                prod_baixa_sel = st.selectbox("Selecione o item para dar baixa:", lista_baixa, key="baixa_sel")
                id_baixa = int(prod_baixa_sel.split("|")[0].split("-")[1])
                prod_baixa_bd = session.query(Estoque).filter_by(id=id_baixa).first()
                
                col_b1, col_b2 = st.columns([1, 2])
                with col_b1:
                    qtd_consumo = st.number_input("Quantidade Utilizada:", min_value=0.0, step=1.0)
                with col_b2:
                    st.write("") # Alinhamento visual
                    st.write("")
                    if st.button("Confirmar Saída do Almoxarifado", use_container_width=True):
                        if prod_baixa_bd and qtd_consumo > 0 and prod_baixa_bd.quantidade >= qtd_consumo:
                            prod_baixa_bd.quantidade -= qtd_consumo
                            session.commit()
                            st.success("Baixa de consumo processada com sucesso!")
                            st.rerun()
                        else:
                            st.error("Quantidade inválida ou saldo insuficiente para baixa.")
            else:
                st.info("Almoxarifado sem saldos ativos.")
                
        with aba_historico_nf:
            st.write("### Histórico de Recebimento de Documentos Fiscais")
            if todas_nfs:
                # Faz um cruzamento em memória para exibir o nome do produto ao lado do número da NF
                mapa_nomes_produtos = {p.id: p.nome_material for p in todos_produtos}
                
                df_nf = pd.DataFrame([{
                    "Número NF-e": n.numero_nf,
                    "Fornecedor / Emitente": n.fornecedor,
                    "Código Material": f"MAT-{n.produto_id:04d}",
                    "Material Vinculado": mapa_nomes_produtos.get(n.produto_id, "Desconhecido"),
                    "Volume Recebido": n.quantidade_recebida,
                    "Data de Chegada": n.data_recebimento.strftime('%d/%m/%Y')
                } for n in todas_nfs])
                st.dataframe(df_nf, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma Nota Fiscal lançada no livro de registro ainda.")


session.close()