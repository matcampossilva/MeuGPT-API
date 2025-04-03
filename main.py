# ... [todo o import e load_dotenv exatamente igual]

# === Coloca essa função nova pra validar nome ===
def nome_valido(text):
    if not text:
        return False
    partes = text.strip().split()
    if len(partes) < 2:
        return False
    if any(char in text for char in "@!?0123456789#%$*"):
        return False
    return True

# ... [resto igual até o webhook]

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    if not os.path.exists("conversas"):
        os.makedirs("conversas")

    status = get_user_status(from_number)

    # NOVO USUÁRIO → Só responde com mensagem de boas-vindas, não salva nada ainda
    if status == "Novo":
        if is_boas_vindas(incoming_msg):
            send_message(from_number,
                "Olá! Sou o Meu Conselheiro Financeiro criado pelo Matheus Campos, CFP®. "
                "Tô aqui pra te ajudar a organizar suas finanças e sua vida, sempre colocando Deus, sua família e seu trabalho antes do dinheiro. "
                "Me conta uma coisa: Qual é seu maior objetivo financeiro hoje?")
            return {"status": "mensagem de boas-vindas enviada"}

        # Cria o usuário na planilha após a primeira mensagem *não genérica*
        sheet = get_user_sheet(from_number)
        values = sheet.col_values(2)
        row = values.index(from_number) + 1 if from_number in values else None
    else:
        sheet = get_user_sheet(from_number)
        values = sheet.col_values(2)
        row = values.index(from_number) + 1 if from_number in values else None

    # Valida e recupera nome/email
    name = sheet.cell(row, 1).value.strip() if sheet.cell(row, 1).value else ""
    email = sheet.cell(row, 3).value.strip() if sheet.cell(row, 3).value else ""

    # BLOQUEIO POR LIMITE
    if passou_limite(sheet, row):
        send_message(from_number,
            "⚠️ Você atingiu o limite gratuito de 10 interações.\n\n"
            "Pra continuar com seu conselheiro financeiro pessoal (que é mais paciente que muita gente), acesse: https://seulinkpremium.com")
        return {"status": "limite atingido"}

    # ONBOARDING (nome e email)
    captured_email = extract_email(incoming_msg) if not email else None
    captured_name = incoming_msg if not name and nome_valido(incoming_msg) else None

    if not name or not email:
        if captured_name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number,
                "Antes de qualquer coisa, preciso só de dois detalhes essenciais pra te ajudar de verdade:\n\n"
                "👉 Seu nome completo\n👉 Seu e-mail\n\nPode mandar os dois aqui mesmo 🙌")
            return {"status": "aguardando nome e email"}

        if name and not email:
            send_message(from_number, "Faltou só o e-mail. Vai lá, sem medo. 🙏")
            return {"status": "aguardando email"}

        if email and not name:
            send_message(from_number,
                "Faltou o nome completo — aquele que você usaria pra assinar um contrato importante. ✍️")
            return {"status": "aguardando nome"}

        if name and email:
            welcome_msg = f"""Perfeito, {name}! 👊

Seus dados estão registrados. Agora sim, podemos começar de verdade. 😊

Estou aqui pra te ajudar com suas finanças, seus investimentos, decisões sobre empréstimos e até com orientações práticas de vida espiritual e familiar.

Me conta: qual é a principal situação financeira que você quer resolver hoje?"""
            send_message(from_number, welcome_msg)
            return {"status": "cadastro completo"}

    # MEMÓRIA DE CONVERSA
    conversa_path = f"conversas/{from_number}.txt"
    with open(conversa_path, "a") as f:
        f.write(f"Usuário: {incoming_msg}\n")

    prompt_base = open("prompt.txt", "r").read()
    historico = open(conversa_path, "r").read()

    full_prompt = f"""{prompt_base}

{historico}
Conselheiro:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.7,
    )

    reply = response["choices"][0]["message"]["content"].strip()

    with open(conversa_path, "a") as f:
        f.write(f"Conselheiro: {reply}\n")

    tokens = count_tokens(incoming_msg) + count_tokens(reply)
    sheet.update_cell(row, 5, int(sheet.cell(row, 5).value or 0) + tokens)
    increment_interactions(sheet, row)

    send_message(from_number, reply)
    return {"status": "mensagem enviada"}