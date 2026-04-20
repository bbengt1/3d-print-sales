BUSINESS_SETTINGS_DATA = [
    ("currency", "USD", "Currency code"),
    ("default_profit_margin_pct", "40", "Target markup on total cost"),
    ("platform_fee_pct", "9.5", "Etsy/Amazon/etc."),
    ("fixed_fee_per_order", "0.45", "Per-transaction fee"),
    ("sales_tax_pct", "0", "Set if you collect tax"),
    ("electricity_cost_per_kwh", "0.18", "Check your utility bill"),
    ("printer_power_draw_watts", "120", "Average draw while printing"),
    ("failure_rate_pct", "5", "Buffer for failed prints"),
    ("packaging_cost_per_order", "1.25", "Boxes, tape, padding"),
    ("shipping_charged_to_customer", "0", "0 = free shipping model"),
]

AI_SETTINGS_DATA = [
    ("ai_provider", "chatgpt", "Selected insights provider: chatgpt, claude, or grok."),
    ("ai_chatgpt_model", "gpt-4.1-mini", "OpenAI model used for read-only business insights."),
    ("ai_chatgpt_api_key", "", "OpenAI API key for ChatGPT insights."),
    ("ai_claude_model", "claude-3-5-sonnet-latest", "Anthropic Claude model used for read-only business insights."),
    ("ai_claude_api_key", "", "Anthropic API key for Claude insights."),
    ("ai_grok_model", "grok-3-mini", "xAI Grok model used for read-only business insights."),
    ("ai_grok_api_key", "", "xAI API key for Grok insights."),
]

LABEL_SETTINGS_DATA = [
    ("barcode_default_format", "code128", "Default barcode format: code128, upc, or qr."),
    ("barcode_label_template", "avery_5160", "Label sheet template: avery_5160 or continuous_roll_2x1."),
    ("barcode_include_price", "false", "Include unit price on printed labels."),
]

SETTINGS_DATA = BUSINESS_SETTINGS_DATA + AI_SETTINGS_DATA + LABEL_SETTINGS_DATA
