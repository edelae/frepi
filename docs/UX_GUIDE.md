# Frepi Agent - UX Guide

Guia de experiência do usuário que define como o bot deve se comportar em diferentes cenários.

---

## Índice

1. [Arquitetura de Agentes](#arquitetura-de-agentes)
2. [Onboarding](#1-onboarding)
3. [Regras de Estilo](#regras-de-estilo)
4. [Mapeo de Base de Dados](#mapeo-de-base-de-dados)
5. [Interações com Base de Dados (Agent Tools)](#interações-com-base-de-dados-agent-tools)
6. [Fluxo de Estados](#fluxo-de-estados)
7. [Tratamento de Erros](#tratamento-de-erros)
8. [Exemplos de Conversação](#exemplos-de-conversação-completa)

---

## Arquitetura de Agentes

### Visão Geral do Sistema Multi-Agente

O Frepi utiliza uma arquitetura de **multi-agentes** onde um agente principal (Restaurant Facing Agent) orquestra subagentes especializados para cada tipo de tarefa. Essa arquitetura permite:

- **Especialização**: Cada subagente é otimizado para sua função específica
- **Manutenção**: Código modular e fácil de atualizar
- **Escalabilidade**: Novos subagentes podem ser adicionados sem afetar os existentes

### Diagrama de Fluxo

```
┌─────────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT (Entry Point)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │ Mensagem do usuário
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│       RESTAURANT FACING AGENT (Orquestrador Principal)          │
│                                                                  │
│  • Detecta se é usuário novo ou existente                       │
│  • Mantém contexto da conversa                                  │
│  • Roteia para subagente apropriado                             │
│  • Exibe menu de 4 opções                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   ONBOARDING    │ │  PRICE UPDATER  │ │ PURCHASE ORDER  │
│    SUBAGENT     │ │    SUBAGENT     │ │   SUBAGENTS     │
│                 │ │                 │ │                 │
│ Novo usuário    │ │ Opção 2️⃣        │ │ Opção 1️⃣        │
│ Opções 3️⃣ e 4️⃣   │ │                 │ │ (+ Followup)    │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SUPABASE (PostgreSQL)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Mapeamento Menu → Subagente

| Opção do Menu | Subagente Responsável | Cenário |
|---------------|----------------------|---------|
| (Automático) | **Onboarding Subagent** | Usuário novo detectado |
| 1️⃣ Fazer uma compra | **Purchase Order Creator** | Compras e pedidos |
| 2️⃣ Atualizar preços | **Supplier Price Updater** | Atualização de preços |
| 3️⃣ Registrar fornecedor | **Onboarding Subagent** | Cadastro de fornecedor |
| 4️⃣ Configurar preferências | **Onboarding Subagent** | Preferências de produto |
| (Após pedido criado) | **Purchase Order Followup** | Acompanhamento de pedidos |

### Subagentes e suas Responsabilidades

#### 1. Onboarding Subagent
**Localização**: `frepi_agent/restaurant_facing_agent/subagents/onboarding_subagent/`

| Responsabilidade | Descrição |
|-----------------|-----------|
| Registro de usuário | Detecta número novo e coleta dados básicos |
| Parsing de invoices | Processa fotos de notas fiscais com GPT-4 Vision |
| Coleta de preferências | Configura preferências para top 10 produtos |
| Registro de fornecedor | Cadastra novos fornecedores no sistema |

**Tools específicas**:
- `image_parser.py` - Extrai dados de notas fiscais
- `product_preference.py` - Salva preferências de produto
- `supplier_registration.py` - Registra novos fornecedores

#### 2. Supplier Price Updater Subagent
**Localização**: `frepi_agent/restaurant_facing_agent/subagents/supplier_price_updater/`

| Responsabilidade | Descrição |
|-----------------|-----------|
| Verificar fornecedor | Confirma que fornecedor existe |
| Coletar preços | Recebe atualizações de preço do usuário |
| Atualizar histórico | Salva preços em `pricing_history` |

#### 3. Purchase Order Creator Subagent
**Localização**: `frepi_agent/restaurant_facing_agent/subagents/purchase_order_creator/`

| Responsabilidade | Descrição |
|-----------------|-----------|
| Busca de produtos | Busca semântica na lista de produtos do restaurante |
| Comparação de preços | Lista preços de múltiplos fornecedores |
| Validação de preços | Verifica se preços estão atualizados |
| Criação de pedido | Finaliza e registra o pedido |

#### 4. Purchase Order Followup Subagent
**Localização**: `frepi_agent/restaurant_facing_agent/subagents/purchase_order_followup/`

| Responsabilidade | Descrição |
|-----------------|-----------|
| Status do pedido | Informa situação atual |
| Histórico | Lista pedidos anteriores |
| Atualizações | Notifica sobre entregas |

### Tools por Subagente

#### Onboarding Subagent Tools

| Tool | Arquivo | Função |
|------|---------|--------|
| `parse_invoice_image` | `image_parser.py` | Extrai dados de foto de nota fiscal |
| `save_product_preference` | `product_preference.py` | Salva preferência em `restaurant_product_preferences` |
| `register_supplier` | `supplier_registration.py` | Cria registro em `suppliers` |

#### Shared Tools (Usadas por todos os subagentes)

| Tool | Arquivo | Função | Tabelas |
|------|---------|--------|---------|
| `search_products` | `product_search.py` | Busca semântica | `master_list` |
| `get_product_prices` | `pricing.py` | Obtém preços | `pricing_history`, `suppliers` |
| `validate_product_prices` | `pricing.py` | Valida frescor | `pricing_history` |
| `check_supplier` | `suppliers.py` | Verifica existência | `suppliers` |
| `get_suppliers_for_product` | `suppliers.py` | Lista fornecedores | `supplier_mapped_products`, `suppliers` |

---

## 1. Onboarding

### Visão Geral

O onboarding é o processo de registro de novos usuários no sistema. O bot detecta automaticamente números não registrados e inicia o fluxo de cadastro.

### Fases do Onboarding

| Fase | Descrição | Duração Estimada |
|------|-----------|------------------|
| 1 | Detecção e escolha (Restaurante/Fornecedor) | 1 mensagem |
| 2 | Registro básico do restaurante (nome, contato, endereço, cidade, cozinha) | 5-6 mensagens |
| 3 | Upload de notas fiscais | Variável |
| 4 | Extração e análise de dados | Automático |
| 5 | Configuração de preferências (Top 10) | 10-20 mensagens |

---

### Fase 1: Detecção de Usuário Novo

**Trigger**: Mensagem recebida de número não registrado na tabela `telegram_users`

**Resposta do Bot**:
```
👋 Bem-vindo ao Frepi!

Vejo que você é um número novo. Quer se registrar como:

1️⃣ Restaurante
2️⃣ Fornecedor
```

**Ações do Sistema**:
- Verificar se `telegram_chat_id` existe em `telegram_users`
- Se não existe, iniciar fluxo de onboarding
- Aguardar resposta (1 ou 2)

---

### Fase 2: Registro de Restaurante

Se o usuário seleciona "1" (Restaurante), coletar informações básicas:

#### Pergunta 1: Nome do Restaurante
```
BOT: Perfeito! 🍽️ Vamos configurar sua conta de restaurante.

Qual é o nome do seu restaurante?
```
**Campo DB**: `restaurants.restaurant_name`

#### Pergunta 2: Nome do Contato
```
BOT: Excelente! 📝 [Nome do Restaurante] registrado.

Qual é o seu nome?
```
**Campo DB**: `restaurant_people.full_name`

#### Pergunta 3: Endereço
```
BOT: Prazer, [Nome]! 👋

Qual é o endereço completo do [Nome do Restaurante]?
(Rua, número, bairro)
```
**Campo DB**: `restaurants.street_address`

#### Pergunta 4: Cidade
```
BOT: Endereço registrado 📍

Em qual cidade está localizado?
```
**Campo DB**: `restaurants.city`

#### Pergunta 5: Tipo de Cozinha
```
BOT: [Cidade] registrado 📍

Última pergunta: Que tipo de cozinha vocês trabalham?
(Ex: brasileira, italiana, japonesa, variada...)
```
**Campo DB**: `restaurants.restaurant_type`

#### Confirmação do Registro Básico
```
BOT: ✅ Registro básico completado!

**Resumo:**
• Restaurante: [Nome do Restaurante]
• Contato: [Nome do Contato]
• Endereço: [Endereço]
• Cidade: [Cidade]
• Cozinha: [Tipo de Cozinha]
```

**Ações do Sistema**:
1. Criar registro em `restaurants` com `onboarding_status = 'basic_info'`
2. Criar registro em `restaurant_people` vinculado ao restaurante
3. Criar registro em `telegram_users` mapeando chat_id → restaurant_id

---

### Fase 3: Upload de Notas Fiscais

**Solicitação do Bot**:
```
📸 Agora, para personalizar sua experiência, pode nos enviar fotos das suas notas fiscais de compra dos últimos 30 dias?

Isso nos ajuda a:
• Conhecer seus fornecedores atuais
• Identificar os produtos que você mais compra
• Dar melhores recomendações de preço

Envie as fotos uma por uma. Quando terminar, escreva "pronto" ✨
```

#### Ao Receber Cada Foto
```
BOT: 📄 Nota fiscal recebida! Processando...

✅ Identifiquei:
• Fornecedor: [Nome do Fornecedor]
• [X] produtos
• Data: [DD/MM/YYYY]

Tem mais notas fiscais? Envie ou escreva "pronto" quando terminar.
```

#### Ao Receber "pronto"
```
BOT: 📊 Excelente! Analisei suas notas fiscais.

**Resumo:**
• [X] fornecedores identificados
• [Y] produtos encontrados
• R$ [Z] em compras totais

**Seus Top 10 produtos mais comprados:**
1. [Produto 1] ([quantidade]/mês)
2. [Produto 2] ([quantidade]/mês)
3. [Produto 3] ([quantidade]/mês)
4. [Produto 4] ([quantidade]/mês)
5. [Produto 5] ([quantidade]/mês)
6. [Produto 6] ([quantidade]/mês)
7. [Produto 7] ([quantidade]/mês)
8. [Produto 8] ([quantidade]/mês)
9. [Produto 9] ([quantidade]/mês)
10. [Produto 10] ([quantidade]/mês)

Agora vamos configurar suas preferências para estes produtos 🎯
```

**Ações do Sistema**:
1. Salvar foto em Supabase Storage: `invoices/{restaurant_id}/{timestamp}_{filename}`
2. Processar com GPT-4 Vision para extrair:
   - Nome do fornecedor
   - Lista de produtos com quantidades e preços
   - Data da nota fiscal
3. Criar/vincular registros em `suppliers`
4. Buscar/criar produtos em `master_list`
5. Registrar preços em `pricing_history`
6. Calcular Top 10 produtos por frequência/volume
7. Atualizar `onboarding_status = 'invoices_uploaded'`

---

### Fase 4: Extração de Dados (Automática)

Esta fase acontece automaticamente durante o processamento das notas fiscais.

**Dados Extraídos**:

| Dado | Destino | Ação |
|------|---------|------|
| Fornecedores | `suppliers` | Criar se não existe, vincular se existe |
| Produtos | `master_list` | Buscar por similaridade semântica, criar se não encontrar |
| Preços | `pricing_history` | Registrar com data da nota fiscal |
| Mapeamentos | `supplier_mapped_products` | Vincular produto-fornecedor |

---

### Fase 5: Configuração de Preferências

Para cada um dos Top 10 produtos, perguntar sobre preferências:

#### Pergunta de Marca
```
BOT: 🥩 **[Nome do Produto]** - Seu produto #[N]

Tem preferência de marca?

1️⃣ [Marca 1]
2️⃣ [Marca 2]
3️⃣ [Marca 3]
4️⃣ Sem preferência (busco melhor preço)
5️⃣ Outra marca
```

Se seleciona "5" (Outra marca):
```
BOT: Qual marca você prefere para [Produto]?
```

#### Pergunta de Preço Máximo
```
BOT: ✅ Preferência salva: [Marca] para [Produto]

Qual é o preço máximo que você pagaria por [unidade]?
(Preço atual médio: R$ [X,XX]/[unidade])
```

#### Confirmação
```
BOT: ✅ Limite de preço: R$ [X,XX]/[unidade]
```

**Campo DB**: `restaurant_product_preferences`
- `brand_preferences`: Array de marcas preferidas
- `price_preference`: Preço máximo aceitável

---

### Finalização do Onboarding

Após configurar preferências dos 10 produtos:

```
BOT: 🎉 Configuração completada!

**Seu perfil:**
• Restaurante: [Nome]
• Fornecedores: [X] registrados
• Produtos: [Y] na sua lista
• Preferências: 10 produtos configurados

---

O que você gostaria de fazer agora?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências
```

**Ações do Sistema**:
1. Atualizar `onboarding_status = 'completed'`
2. Transicionar para o fluxo normal do bot (menu de 4 opções)

---

## Regras de Estilo

### Idioma
- **Português (BR) somente**
- Tom semi-formal e amigável
- Usar "você" (não "tu" ou "o senhor")

### Emojis
Usar estrategicamente:
| Emoji | Uso |
|-------|-----|
| 👋 | Saudações |
| ✅ | Confirmações de sucesso |
| ⚠️ | Alertas e avisos |
| 📸 | Upload de fotos |
| 📄 | Documentos/Notas fiscais |
| 📊 | Resumos e estatísticas |
| 🎯 | Objetivos e próximos passos |
| 💰 | Preços e valores |
| 📦 | Produtos e pedidos |
| 🍽️ | Restaurante |
| 📍 | Localização |
| 📝 | Registro de dados |
| 🎉 | Celebração/Conclusão |

### Tamanho das Mensagens
- **Médio**: Nem muito curtas nem muito longas
- Usar listas com bullets (•) para organizar informações
- Separar seções com `---` quando necessário

### Menu de Opções
- **Sempre** mostrar opções numeradas com emojis (1️⃣, 2️⃣, etc.)
- Máximo 5 opções por mensagem
- Incluir opção "Outra" quando aplicável

### Confirmações
- **Sempre** confirmar dados salvos
- Mostrar resumo antes de avançar para próxima fase

---

## Mapeo de Base de Dados

### Tabelas Envolvidas no Onboarding

| Tabela | Propósito | Campos Principais |
|--------|-----------|-------------------|
| `telegram_users` | Mapear chat_id → restaurant | `telegram_chat_id`, `restaurant_id`, `user_type` |
| `restaurants` | Perfil do restaurante | `restaurant_name`, `city`, `restaurant_type`, `onboarding_status` |
| `restaurant_people` | Contato/usuário | `full_name`, `whatsapp_number`, `restaurant_id` |
| `suppliers` | Fornecedores extraídos | `company_name`, `is_active` |
| `master_list` | Lista de produtos do restaurante (preferências, specs) | `product_name`, `embedding_vector_v2` |
| `supplier_mapped_products` | Mapeamento produto-fornecedor | `master_list_id`, `supplier_id` |
| `pricing_history` | Preços das notas | `unit_price`, `effective_date` |
| `restaurant_product_preferences` | Preferências configuradas | `brand_preferences`, `price_preference` |

### Nova Tabela: telegram_users

```sql
CREATE TABLE IF NOT EXISTS telegram_users (
  telegram_chat_id BIGINT PRIMARY KEY,
  restaurant_id INT REFERENCES restaurants(id),
  restaurant_person_id INT REFERENCES restaurant_people(id),
  supplier_id INT REFERENCES suppliers(id),
  user_type VARCHAR(20) NOT NULL, -- 'restaurant' ou 'supplier'
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_telegram_users_restaurant ON telegram_users(restaurant_id);
CREATE INDEX idx_telegram_users_supplier ON telegram_users(supplier_id);
```

### Novo Campo: onboarding_status

```sql
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS
  onboarding_status VARCHAR(50) DEFAULT 'pending';

-- Valores possíveis:
-- 'pending'           - Não iniciou onboarding
-- 'basic_info'        - Completou registro básico
-- 'invoices_uploaded' - Enviou notas fiscais
-- 'preferences_set'   - Configurou preferências
-- 'completed'         - Onboarding completo
```

### Armazenamento de Fotos

| Aspecto | Configuração |
|---------|--------------|
| Plataforma | Supabase Storage |
| Bucket | `invoices` |
| Estrutura | `/{restaurant_id}/{timestamp}_{filename}` |
| Exemplo | `/123/1705320000_nota_fiscal.jpg` |
| Retenção | Permanente (para referência futura) |

---

## Interações com Base de Dados (Agent Tools)

Esta seção documenta como os subagentes interagem com a base de dados através das ferramentas (tools) disponíveis.

> **Nota**: As tools estão organizadas em dois grupos: **Shared Tools** (usadas por múltiplos subagentes) e **Subagent-specific Tools** (exclusivas de um subagente). Veja a seção [Arquitetura de Agentes](#arquitetura-de-agentes) para entender qual subagente usa cada tool.

### Visão Geral das Tools do Agente

Os subagentes têm acesso a 5 ferramentas compartilhadas + tools específicas via function calling:

| Tool | Função | Propósito | Usado Por |
|------|--------|-----------|-----------|
| `search_products` | `product_search.search_products()` | Busca semântica de produtos | Purchase Order Creator, Onboarding |
| `get_product_prices` | `pricing.get_prices_for_product()` | Obter preços de um produto | Purchase Order Creator |
| `validate_product_prices` | `pricing.validate_prices()` | Verificar frescor dos preços | Purchase Order Creator |
| `check_supplier` | `suppliers.check_supplier_exists()` | Verificar se fornecedor existe | Supplier Price Updater, Onboarding |
| `get_suppliers_for_product` | `suppliers.get_suppliers_for_product()` | Obter fornecedores de um produto | Purchase Order Creator |

---

### Tool 1: search_products

**Propósito**: Buscar produtos na lista do restaurante (`master_list`) usando similaridade semântica (embeddings).

**Fluxo de Dados**:
```
Entrada: query (texto do usuário, ex: "picanha")
    ↓
generate_embedding(query)  →  OpenAI text-embedding-3-small
    ↓
execute_rpc("vector_search")  →  pgvector similarity search
    ↓
Retorna: Lista de ProductMatch com scores de similaridade
```

**Tabelas Acessadas**:

| Tabela | Colunas | Filtros | Operação |
|--------|---------|---------|----------|
| `master_list` | `id`, `product_name`, `brand`, `specifications`, `embedding_vector_v2` | `is_active = true`, `LIMIT 4` | SELECT (Vector Search) |

**Dados Retornados**:
```python
SearchResult(
    query="picanha",
    matches=[
        ProductMatch(
            id=1,
            product_name="Picanha Friboi Premium",
            brand="Friboi",
            specifications={"weight": "1.2kg", "type": "Bovina"},
            similarity=0.92,
            confidence="HIGH"  # HIGH >0.85, MEDIUM 0.70-0.85, LOW <0.70
        ),
        # ... até 4 matches
    ],
    has_high_confidence=True,
    best_match=ProductMatch(...)
)
```

**Exemplo de Uso pelo Bot**:
```
USUÁRIO: Quero comprar picanha

BOT: [Chama search_products("picanha")]

Encontrei esses produtos:
✅ Picanha Friboi Premium (92% match)
📦 Picanha Marfrig (88% match)
```

---

### Tool 2: get_product_prices

**Propósito**: Obter todos os preços disponíveis para um produto específico.

**Fluxo de Dados**:
```
Entrada: product_id (int)
    ↓
execute_rpc("get_product_prices") OR fallback queries
    ↓
JOIN: pricing_history + supplier_mapped_products + suppliers + master_list
    ↓
Retorna: Lista de PriceInfo ordenada por preço (ASC)
```

**Tabelas Acessadas**:

| Tabela | Colunas | Filtros | Operação |
|--------|---------|---------|----------|
| `pricing_history` | `id`, `unit_price`, `unit`, `effective_date`, `end_date` | `end_date IS NULL` | SELECT |
| `supplier_mapped_products` | `id`, `supplier_id`, `supplier_product_name`, `master_list_id` | `master_list_id = {product_id}` | SELECT |
| `suppliers` | `id`, `company_name` | `id IN (supplier_ids)` | SELECT |
| `master_list` | `id`, `product_name` | `id = {product_id}` | SELECT |

**Dados Retornados**:
```python
[
    PriceInfo(
        product_id=1,
        product_name="Picanha Friboi Premium",
        supplier_id=10,
        supplier_name="Friboi Direto",
        unit_price=41.90,
        unit="kg",
        effective_date=datetime(2025, 1, 10),
        days_old=8,
        is_fresh=True  # True se days_old <= 30
    ),
    PriceInfo(
        product_id=1,
        product_name="Picanha Friboi Premium",
        supplier_id=15,
        supplier_name="Frigorífico Central",
        unit_price=43.50,
        unit="kg",
        effective_date=datetime(2025, 1, 5),
        days_old=13,
        is_fresh=True
    ),
]
```

**Exemplo de Uso pelo Bot**:
```
USUÁRIO: Qual o preço da picanha?

BOT: [Chama get_product_prices(product_id=1)]

💰 Preços para Picanha Friboi Premium:

✅ Friboi Direto - R$ 41,90/kg
   • Preço atualizado há 8 dias

📦 Frigorífico Central - R$ 43,50/kg
   • Preço atualizado há 13 dias
```

---

### Tool 3: validate_product_prices

**Propósito**: Verificar se os preços de múltiplos produtos estão atualizados (frescos).

**Fluxo de Dados**:
```
Entrada: product_ids (lista), freshness_days (default: 30)
    ↓
get_prices_for_products(product_ids)  →  Loop por cada produto
    ↓
Para cada preço: verificar se days_old <= freshness_days
    ↓
Retorna: PriceValidationResult com produtos válidos, stale e sem preço
```

**Tabelas Acessadas**: Mesmas de `get_product_prices`, para cada produto.

**Dados Retornados**:
```python
PriceValidationResult(
    valid_products=[1, 3, 5],      # Têm preços frescos
    stale_products=[2],             # Preços > 30 dias
    missing_products=[4],           # Sem preços registrados
    all_valid=False,
    details={
        1: {"has_price": True, "is_fresh": True, "days_old": 8},
        2: {"has_price": True, "is_fresh": False, "days_old": 45},
        4: {"has_price": False, "is_fresh": False, "days_old": None},
    }
)
```

**Exemplo de Uso pelo Bot**:
```
USUÁRIO: Quero comprar picanha e camarão

BOT: [Chama validate_product_prices([1, 4])]

✅ Picanha - Preço disponível (R$ 41,90/kg)
⚠️ Camarão - Sem preço registrado

Posso prosseguir com a picanha. Para o camarão,
preciso contatar os fornecedores primeiro.
```

---

### Tool 4: check_supplier

**Propósito**: Verificar se um fornecedor existe no sistema pelo nome.

**Fluxo de Dados**:
```
Entrada: company_name (texto)
    ↓
get_supplier_by_name(company_name)  →  Busca case-insensitive
    ↓
Retorna: Boolean + dados do fornecedor se encontrado
```

**Tabelas Acessadas**:

| Tabela | Colunas | Filtros | Operação |
|--------|---------|---------|----------|
| `suppliers` | `*` (todas) | `company_name ILIKE %{name}%`, `LIMIT 1` | SELECT |

**Colunas Retornadas do Supplier**:
- `id` (int)
- `company_name` (string)
- `contact_person` (string)
- `phone` (string)
- `email` (string)
- `cnpj` (string)
- `address` (string)
- `is_active` (boolean)
- `reliability_score` (float)
- `response_time_avg` (float)

**Dados Retornados**:
```python
{
    "exists": True,
    "supplier": {
        "id": 10,
        "company_name": "Friboi Direto",
        "contact_person": "João Silva",
        "phone": "11999887766",
        "is_active": True,
        "reliability_score": 0.97
    }
}
# ou
{
    "exists": False,
    "supplier": None
}
```

**Exemplo de Uso pelo Bot**:
```
USUÁRIO: Quero atualizar os preços do fornecedor Marfrig

BOT: [Chama check_supplier("Marfrig")]

✅ Fornecedor encontrado: Marfrig Distribuidora
Confiabilidade: 95%

Quais produtos você quer atualizar?
```

---

### Tool 5: get_suppliers_for_product

**Propósito**: Obter lista de fornecedores que vendem um produto específico.

**Fluxo de Dados**:
```
Entrada: product_id (int)
    ↓
Query supplier_mapped_products  →  Obter supplier_ids
    ↓
Query suppliers  →  Obter detalhes dos fornecedores
    ↓
Retorna: Lista de Supplier (filtrados por is_active)
```

**Tabelas Acessadas**:

| Tabela | Colunas | Filtros | Operação |
|--------|---------|---------|----------|
| `supplier_mapped_products` | `supplier_id` | `master_list_id = {product_id}` | SELECT |
| `suppliers` | `*` (todas) | `id IN (supplier_ids)`, `is_active = true` | SELECT |

**Dados Retornados**:
```python
{
    "product_id": 1,
    "suppliers": [
        Supplier(
            id=10,
            company_name="Friboi Direto",
            reliability_score=0.97,
            response_time_avg=2.5,
            is_active=True
        ),
        Supplier(
            id=15,
            company_name="Frigorífico Central",
            reliability_score=0.95,
            response_time_avg=4.0,
            is_active=True
        ),
    ],
    "count": 2
}
```

**Exemplo de Uso pelo Bot**:
```
USUÁRIO: Quem vende picanha?

BOT: [Chama get_suppliers_for_product(product_id=1)]

📦 Fornecedores de Picanha Friboi Premium:

1. Friboi Direto
   • Confiabilidade: 97%
   • Tempo de resposta: 2.5 dias

2. Frigorífico Central
   • Confiabilidade: 95%
   • Tempo de resposta: 4.0 dias
```

---

### Resumo: Operações por Tabela e Subagente

| Tabela | SELECT | INSERT | UPDATE | Subagente(s) | Tool(s) |
|--------|--------|--------|--------|--------------|---------|
| `master_list` | ✅ | ✅* | ❌ | Purchase Order Creator, Onboarding | search_products |
| `pricing_history` | ✅ | ✅ | ✅ | Purchase Order Creator, Price Updater | get_product_prices, update_price |
| `supplier_mapped_products` | ✅ | ✅* | ❌ | Purchase Order Creator, Onboarding | get_suppliers_for_product |
| `suppliers` | ✅ | ✅ | ✅ | Price Updater, Onboarding | check_supplier, supplier_registration |
| `restaurants` | ✅ | ✅ | ✅ | Onboarding | (onboarding tools) |
| `restaurant_people` | ✅ | ✅ | ✅ | Onboarding | (onboarding tools) |
| `restaurant_product_preferences` | ✅ | ✅ | ✅ | Onboarding | product_preference |
| `telegram_users` | ✅ | ✅ | ✅ | Onboarding | (onboarding tools) |

*Funções marcadas com * são usadas durante o onboarding para criar novos produtos/mapeamentos.

---

### Funções RPC do Supabase

O sistema usa duas funções RPC para otimizar queries complexas:

#### 1. vector_search
```sql
CREATE OR REPLACE FUNCTION vector_search(
  query_embedding vector(1536),
  search_term text DEFAULT '',
  match_count int DEFAULT 10
)
RETURNS TABLE (
  id bigint,
  product_name text,
  brand text,
  specifications jsonb,
  similarity_distance float
)
```

#### 2. get_product_prices
```sql
CREATE OR REPLACE FUNCTION get_product_prices(p_product_id bigint)
RETURNS TABLE (
  price_id bigint,
  product_id bigint,
  product_name text,
  supplier_id int,
  supplier_name text,
  unit_price numeric,
  unit text,
  effective_date timestamp
)
```

---

### Thresholds de Configuração

| Configuração | Valor Default | Usado Por |
|--------------|---------------|-----------|
| `price_freshness_days` | 30 | validate_product_prices |
| `high_confidence_threshold` | 0.85 | search_products |
| `medium_confidence_threshold` | 0.70 | search_products |
| `vector_search_limit` | 4 | search_products |

---

### Fluxo Típico: Compra de Produto

```
1. USUÁRIO: "Quero comprar 10kg de picanha"

2. BOT chama search_products("picanha")
   → master_list (vector search)
   → Retorna: Picanha Friboi Premium (92% match)

3. BOT chama get_product_prices(product_id=1)
   → pricing_history + supplier_mapped_products + suppliers
   → Retorna: 2 fornecedores com preços

4. BOT chama validate_product_prices([1])
   → Verifica: preços < 30 dias? ✅
   → Retorna: valid_products=[1]

5. BOT apresenta opções:
   "Picanha Friboi Premium - 10kg:
   ✅ Friboi Direto: R$ 419,00
   📦 Frigorífico Central: R$ 435,00

   Confirma o pedido?"
```

---

## Fluxo de Estados

```
[Novo Usuário]
      │
      ▼
┌─────────────┐
│   pending   │ ◄── Estado inicial
└─────┬───────┘
      │ Completa registro básico
      ▼
┌─────────────┐
│ basic_info  │
└─────┬───────┘
      │ Envia notas fiscais
      ▼
┌──────────────────┐
│ invoices_uploaded │
└─────┬────────────┘
      │ Configura preferências
      ▼
┌─────────────────┐
│ preferences_set │
└─────┬───────────┘
      │ Finaliza onboarding
      ▼
┌─────────────┐
│  completed  │ ◄── Acesso completo ao bot
└─────────────┘
```

---

## Tratamento de Erros

### Usuário não envia foto válida
```
BOT: ⚠️ Não consegui processar essa imagem.

Por favor, envie uma foto clara da nota fiscal.
Dicas:
• Boa iluminação
• Texto legível
• Foto não cortada
```

### Não consegue identificar fornecedor
```
BOT: 📄 Nota fiscal recebida!

⚠️ Não consegui identificar o fornecedor automaticamente.
Qual é o nome do fornecedor desta nota?
```

### Usuário quer pular fase de notas fiscais
```
USUÁRIO: não tenho notas / pular

BOT: Sem problema! 📝

Você pode enviar as notas fiscais depois.
Vamos pular para configurar suas preferências manualmente.

Quais são os 10 produtos que você mais compra?
(Digite um por linha ou separados por vírgula)
```

### Usuário quer cancelar onboarding
```
USUÁRIO: cancelar / sair

BOT: Entendido! 👋

Seu progresso foi salvo. Quando quiser continuar o cadastro, é só me mandar uma mensagem.

Até mais!
```

---

## Exemplos de Conversação Completa

### Exemplo 1: Fluxo Completo

```
USUÁRIO: Oi

BOT: 👋 Bem-vindo ao Frepi!

Vejo que você é um número novo. Quer se registrar como:

1️⃣ Restaurante
2️⃣ Fornecedor

USUÁRIO: 1

BOT: Perfeito! 🍽️ Vamos configurar sua conta de restaurante.

Qual é o nome do seu restaurante?

USUÁRIO: Cantina da Nonna

BOT: Excelente! 📝 Cantina da Nonna registrado.

Qual é o seu nome?

USUÁRIO: Maria Silva

BOT: Prazer, Maria! 👋

Qual é o endereço completo do Cantina da Nonna?
(Rua, número, bairro)

USUÁRIO: Rua Augusta, 1500, Consolação

BOT: Endereço registrado 📍

Em qual cidade está localizado?

USUÁRIO: São Paulo

BOT: São Paulo registrado ✅

Última pergunta: Que tipo de cozinha vocês trabalham?
(Ex: brasileira, italiana, japonesa, variada...)

USUÁRIO: Italiana

BOT: ✅ Registro básico completado!

**Resumo:**
• Restaurante: Cantina da Nonna
• Contato: Maria Silva
• Endereço: Rua Augusta, 1500, Consolação
• Cidade: São Paulo
• Cozinha: Italiana

---

📸 Agora, para personalizar sua experiência, pode nos enviar fotos das suas notas fiscais de compra dos últimos 30 dias?

Isso nos ajuda a:
• Conhecer seus fornecedores atuais
• Identificar os produtos que você mais compra
• Dar melhores recomendações de preço

Envie as fotos uma por uma. Quando terminar, escreva "pronto" ✨

USUÁRIO: [Envia foto]

BOT: 📄 Nota fiscal recebida! Processando...

✅ Identifiquei:
• Fornecedor: Frigorífico Bom Corte
• 12 produtos
• Data: 10/01/2025

Tem mais notas fiscais? Envie ou escreva "pronto" quando terminar.

USUÁRIO: pronto

BOT: 📊 Excelente! Analisei suas notas fiscais.

**Resumo:**
• 1 fornecedor identificado
• 12 produtos encontrados
• R$ 2.450,00 em compras totais

**Seus Top 10 produtos mais comprados:**
1. Filé Mignon (8kg/mês)
2. Queijo Parmesão (5kg/mês)
3. Tomate San Marzano (10kg/mês)
4. Azeite Extra Virgem (6L/mês)
5. Farinha de Trigo (15kg/mês)
6. Presunto Parma (3kg/mês)
7. Manjericão Fresco (2kg/mês)
8. Vinho Tinto (12L/mês)
9. Mussarela de Búfala (4kg/mês)
10. Linguiça Calabresa (5kg/mês)

Agora vamos configurar suas preferências para estes produtos 🎯

BOT: 🥩 **Filé Mignon** - Seu produto #1

Tem preferência de marca?

1️⃣ Friboi
2️⃣ Marfrig
3️⃣ Swift
4️⃣ Sem preferência (busco melhor preço)
5️⃣ Outra marca

USUÁRIO: 4

BOT: ✅ Preferência salva: Sem preferência de marca para Filé Mignon

Qual é o preço máximo que você pagaria por kg?
(Preço atual médio: R$ 89,90/kg)

USUÁRIO: 100

BOT: ✅ Limite de preço: R$ 100,00/kg

---

🧀 **Queijo Parmesão** - Seu produto #2

Tem preferência de marca?

1️⃣ Tirolez
2️⃣ Polenghi
3️⃣ Importado Italiano
4️⃣ Sem preferência
5️⃣ Outra marca

[... continua com os 10 produtos ...]

BOT: 🎉 Configuração completada!

**Seu perfil:**
• Restaurante: Cantina da Nonna
• Fornecedores: 1 registrado
• Produtos: 12 na sua lista
• Preferências: 10 produtos configurados

---

O que você gostaria de fazer agora?

1️⃣ Fazer uma compra
2️⃣ Atualizar preços de fornecedor
3️⃣ Registrar/Atualizar fornecedor
4️⃣ Configurar preferências
```

---

## Próximos Cenários (A Documentar)

### Por Subagente

**Purchase Order Creator**:
- [ ] Fluxo de compra (usuário existente)
- [ ] Comparação de preços múltiplos fornecedores
- [ ] Confirmação e criação de pedido

**Supplier Price Updater**:
- [ ] Atualização de preços via mensagem
- [ ] Validação de preços anormais

**Purchase Order Followup**:
- [ ] Acompanhamento de status
- [ ] Histórico de pedidos

**Onboarding Subagent**:
- [ ] Registro de fornecedor (menu opção 3)
- [ ] Configuração de preferências adicionais (menu opção 4)
- [ ] Onboarding de fornecedores (user_type = 'supplier')

### Geral
- [ ] Tratamento de erros gerais
- [ ] Fallbacks entre subagentes

---

*Documento criado em: Janeiro 2025*
*Versão: 1.0*
