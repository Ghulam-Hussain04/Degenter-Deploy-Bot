from groq import Groq
from app.config import GROQ_API_KEY
from app.services.invest_service import prepare_invest, prepare_invest_custom
from app.services.solana_service import prepare_rebalance, get_rebalance_history
from app.services.withdraw_service import prepare_withdraw
from app.services.positions_service import get_user_positions
from app.services.apy_service import get_all_apys
import json

client = Groq(api_key=GROQ_API_KEY)

# ─────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_positions",
            "description": "Get user's current investment positions, APY, and portfolio summary. Use when user asks about their portfolio, positions, balance, or current APY.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_apys",
            "description": "Get current APY rates for all supported protocols. Use when user asks about APYs, rates, or which protocol is best.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_invest",
            "description": "Prepare a RISK-BASED investment plan. Use ONLY when the user does NOT specify protocol names — just an amount and a risk level (any/low/medium/high). The system picks the top 3 protocols automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Total USDC amount to invest"
                    },
                    "risk_profile": {
                        "type": "string",
                        "enum": ["any", "low", "medium", "high"],
                        "description": "Risk preference"
                    }
                },
                "required": ["user_id", "amount", "risk_profile"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_invest_custom",
            "description": "Prepare a CUSTOM investment plan where the user specifies exact protocols and amounts. Use when the user mentions specific protocol names (e.g. 'invest $100 in Kamino', '$50 in Kamino and $30 in Save', 'divide $100 between Meteora and Raydium'). For equal splits, calculate the per-protocol amount yourself before calling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "allocations": {
                        "type": "array",
                        "description": "List of protocol-amount pairs. Compute amounts before calling (e.g. $100 split equally between 2 protocols = $50 each).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "protocol": {
                                    "type": "string",
                                    "enum": ["Kamino", "Marginfi", "Save", "Raydium", "Orca", "Meteora"]
                                },
                                "amount": {
                                    "type": "number",
                                    "description": "USDC amount to invest in this protocol"
                                }
                            },
                            "required": ["protocol", "amount"]
                        }
                    }
                },
                "required": ["user_id", "allocations"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_rebalance",
            "description": "Prepare rebalance of user funds. Supports full rebalance (move all funds) or partial rebalance (move funds from one specific protocol, by fixed $ amount or percentage). Call when user wants to rebalance, move, or redistribute funds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "target_protocol": {
                        "type": "string",
                        "description": "Protocol to move funds INTO. Leave empty to automatically pick the best APY.",
                        "enum": ["Kamino", "Marginfi", "Save", "Raydium", "Orca", "Meteora"]
                    },
                    "from_protocol": {
                        "type": "string",
                        "description": "Only move funds FROM this specific protocol. e.g. 'Orca'. Leave empty to move from all positions.",
                        "enum": ["Kamino", "Marginfi", "Save", "Raydium", "Orca", "Meteora"]
                    },
                    "amount": {
                        "type": "number",
                        "description": "Fixed USDC dollar amount to move. e.g. 50 means move $50. Use this when user says a specific dollar amount."
                    },
                    "percent": {
                        "type": "number",
                        "description": "Percentage of eligible funds to move (0-100). e.g. 50 means move 50%. Use this when user says a percentage."
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_withdraw",
            "description": "Prepare withdrawal. Call when user wants to withdraw funds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rebalance_history",
            "description": "Get rebalance history. Use when user asks about past rebalances or transaction history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    }
]

# ─────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────
def build_system_prompt(user_id: str) -> str:
    return f"""You are Degen Deploy AI — a friendly DeFi yield optimization assistant on Solana.

The current user's ID is: {user_id}
ALWAYS use this user_id when calling any function. Never ask user for their ID.

Supported protocols:
- Kamino (lending, low risk, 0 day lock)
- Save (lending, low risk, 0 day lock)
- Marginfi (lending, medium risk, 0 day lock)
- Raydium (LP, medium risk, 0 day lock)
- Orca (LP, medium risk, 0 day lock)
- Meteora (LP, high risk, 7 day lock)

YOUR RULES:
1. For invest → choose the right tool based on user intent:

   RISK-BASED (no specific protocols mentioned — use prepare_invest):
     - "Invest $100 with low risk" → amount=100, risk_profile="low"
     - "Invest $500 any risk" → amount=500, risk_profile="any"
     - Must have BOTH amount AND risk profile; if missing → ask for it

   CUSTOM PROTOCOL (user names specific protocols — use prepare_invest_custom):
     - "Invest $100 in Kamino" → allocations=[{{"protocol":"Kamino", "amount":100}}]
     - "$50 in Kamino and $30 in Save" → allocations=[{{"protocol":"Kamino","amount":50}},{{"protocol":"Save","amount":30}}]
     - "Divide $100 between Meteora and Raydium" → allocations=[{{"protocol":"Meteora","amount":50}},{{"protocol":"Raydium","amount":50}}]
     - "$100 in Kamino, Save, Orca equally" → each gets 33.33
     - Calculate per-protocol amounts yourself before calling; do NOT ask the user to calculate
     - Meteora has a 7-day lock — mention this clearly to the user

2. For rebalance → determine the mode from user intent:
   FULL rebalance (move everything):
     - "Rebalance to best APY" → call prepare_rebalance with only user_id
     - "Move all to Kamino" → call prepare_rebalance with target_protocol="Kamino"

   PARTIAL rebalance (move fraction of funds):
     - "Move 50% of Orca to Kamino" → from_protocol="Orca", target_protocol="Kamino", percent=50
     - "Move $20 from Raydium to best APY" → from_protocol="Raydium", amount=20
     - "Move half of my Orca" → from_protocol="Orca", percent=50
     - "Move $30 from Orca to Meteora" → from_protocol="Orca", target_protocol="Meteora", amount=30
     - If target_protocol not specified in partial → pick best APY (omit target_protocol)
     - Locked positions are automatically skipped

3. For withdraw → call prepare_withdraw immediately, no questions needed

4. For portfolio/positions → call get_positions immediately

5. For APY rates → call get_all_apys immediately

RESPONSE STYLE:
- Be concise and friendly
- Use emojis sparingly
- Show amounts with $ sign
- Explain lock periods clearly (Meteora has 7-day lock)
- Support English and Hinglish naturally
- After prepare functions → tell user to sign transactions in their wallet
- Never make decisions for the user"""


# ─────────────────────────────────────────
# FUNCTION EXECUTOR
# ─────────────────────────────────────────
async def execute_function(function_name: str, arguments: dict) -> str:
    try:
        if function_name == "get_positions":
            result = await get_user_positions(arguments["user_id"])

        elif function_name == "get_all_apys":
            result = await get_all_apys()

        elif function_name == "prepare_invest":
            result = await prepare_invest(
                user_id=arguments["user_id"],
                amount=float(arguments["amount"]),
                risk_profile=arguments.get("risk_profile", "any")
            )

        elif function_name == "prepare_invest_custom":
            result = await prepare_invest_custom(
                user_id=arguments["user_id"],
                allocations=arguments["allocations"]
            )

        elif function_name == "prepare_rebalance":
            result = await prepare_rebalance(
                user_id=arguments["user_id"],
                target_protocol=arguments.get("target_protocol"),
                from_protocol=arguments.get("from_protocol"),
                amount=float(arguments["amount"]) if arguments.get("amount") else None,
                percent=float(arguments["percent"]) if arguments.get("percent") else None,
            )

        elif function_name == "prepare_withdraw":
            result = await prepare_withdraw(
                user_id=arguments["user_id"]
            )

        elif function_name == "get_rebalance_history":
            result = await get_rebalance_history(
                user_id=arguments["user_id"]
            )

        else:
            result = {"error": f"Unknown function: {function_name}"}

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────
# MAIN CHAT FUNCTION
# ─────────────────────────────────────────
async def chat(user_id: str, message: str, conversation_history: list = []):
    """
    Proper multi-turn chat with Groq:
    1. Inject user_id into system prompt
    2. Maintain conversation history
    3. Handle clarifying questions
    4. Execute functions when ready
    """

    # Build messages with user_id in system prompt
    messages = [
        {"role": "system", "content": build_system_prompt(user_id)}
    ] + conversation_history + [
        {"role": "user", "content": message}
    ]

    # First Groq call
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=1024,
        temperature=0.3  # Lower = more consistent behavior
    )

    response_message = response.choices[0].message

    # ── Case 1: Groq wants to call a function ──
    if response_message.tool_calls:
        tool_call = response_message.tool_calls[0]
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print(f"🔧 Groq calling function: {function_name}")
        print(f"📦 Arguments: {arguments}")

        # Execute function
        function_result = await execute_function(function_name, arguments)

        print(f"✅ Function result: {function_result[:200]}...")

        # Add assistant message + tool result to history
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": tool_call.function.arguments
                    }
                }
            ]
        })

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": function_result
        })

        # Second Groq call to format the result
        # Must pass tools + tool_choice="none" so Groq doesn't try to call
        # another tool when it sees tool_calls in the conversation history.
        final_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=TOOLS,
            tool_choice="none",
            max_tokens=1024,
            temperature=0.3
        )

        final_text = final_response.choices[0].message.content

        return {
            "reply": final_text,
            "function_called": function_name,
            "function_result": json.loads(function_result),
            # Return updated history for frontend to store
            "updated_history": [
                *conversation_history,
                {"role": "user", "content": message},
                {"role": "assistant", "content": final_text}
            ]
        }

    # ── Case 2: Groq is asking a clarifying question ──
    return {
        "reply": response_message.content,
        "function_called": None,
        "function_result": None,
        # Return updated history for frontend to store
        "updated_history": [
            *conversation_history,
            {"role": "user", "content": message},
            {"role": "assistant", "content": response_message.content}
        ]
    }

