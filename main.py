# ... (seu código de import e variáveis permanece igual)

# === NOVO: Função para contar interações ===
def get_interactions(sheet, row):
    try:
        val = sheet.cell(row, 6).value
        return int(val) if val else 0
    except:
        return 0

def increment_interactions(sheet, row):
    count = get_interactions(sheet, row) + 1
    sheet.update_cell(row, 6, count)
    return count

# === NOVO: Verificação se é gratuito e passou limite ===
def passou_limite(sheet, row):
    status = sheet.title
    if status != "Gratuitos":
        return False
    return get_interactions(sheet, row) >= 10

# === ENDPOINT PRINCIPAL ===
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    # PLANILHA DO USUÁRIO
    sheet = get_user_sheet(from_number)
    values = sheet.col_values(2)
    row = values.index(from_number) + 1 if from_number in values else None

    name = sheet.cell(row, 1).value.strip() if sheet.cell(row, 1).value else ""
    email = sheet.cell(row, 3).value.strip() if sheet.cell(row, 3).value else ""

    # SE PASSOU LIMITE (ANTES DE QUALQUER OUTRA COISA)
    if passou_limite(sheet, row):
        send_message(from_number, "⚠️ Você atingiu o limite gratuito de 10 interações.\n\nPara continuar com seu conselheiro financeiro pessoal, acesse: https://seulinkpremium.com")
        return {"status": "limite atingido"}

    # COLETA DE NOME E EMAIL COM VALIDAÇÃO
    captured_email = extract_email(incoming_msg) if not email else None
    captured_name = extract_name(incoming_msg) if not name else None

    if not name or not email:
        if captured_name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number, "Olá! 👋 Que bom ter você aqui.\n\nPara começarmos nossa jornada financeira juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?")
            return {"status": "aguardando nome e email"}

        if name and not email:
            send_message(from_number, "Só falta o e-mail agora pra eu liberar seu acesso. Pode mandar! 📧")
            return {"status": "aguardando email"}

        if email and not name:
            send_message(from_number, "Faltou só o nome completo. Pode mandar! ✍️")
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
    if not os.path.exists(conversa_path):
        with open(conversa_path, "w") as f:
            f.write("")

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

    # === NOVO: INCREMENTA INTERAÇÃO ===
    increment_interactions(sheet, row)

    send_message(from_number, reply)
    return {"status": "mensagem enviada"}

# === NOVO: /health endpoint ===
@app.get("/health")
def health_check():
    return {"status": "vivo e levemente instável"}