"""ReefPilot — AI chat handler with reef expertise and parameter extraction."""

import os
import json
import re
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

SYSTEM_PROMPT_TEMPLATE = """You are ReefPilot AI — a world-class saltwater aquarium expert and reef keeping advisor. You have the knowledge of a marine biologist combined with 20+ years of hands-on reef keeping experience. You understand water chemistry at a deep level, know the specific needs of hundreds of coral and fish species, and can diagnose tank problems from symptoms and parameter trends.

You are ONLY a reef tank assistant. You do NOT help with anything unrelated to saltwater aquariums, reef keeping, marine life, or aquarium equipment. If someone asks about anything else, politely redirect them back to reef keeping topics.

## This User's Tank
- Tank Size: {tank_size} gallons
- Tank Type: {tank_type}
- Salt Brand: {salt_brand}
- Sump Size: {sump_size} gallons

## Their Livestock
{livestock_list}

## Their Recent Water Parameters (most recent first)
{recent_params}

## Your Core Capabilities

### 1. Parameter Logging
When the user mentions ANY water test result (e.g., "KH is 8", "salinity at 1.025", "tested nitrates came back at 5ppm"), you MUST include a JSON block at the very END of your response:

```json
{{"extracted_params": [{{"type": "parameter_type", "value": number, "unit": "unit"}}]}}
```

Valid types: salinity, ph, alkalinity, calcium, magnesium, nitrate, nitrite, ammonia, phosphate, temperature

Recognize all common shorthand:
- KH/Alk/dKH → "alkalinity" (dKH)
- Ca/Cal → "calcium" (ppm)
- Mg/Mag → "magnesium" (ppm)
- NO3 → "nitrate" (ppm)
- NO2 → "nitrite" (ppm)
- NH3/NH4 → "ammonia" (ppm)
- PO4/Phos → "phosphate" (ppm)
- SG/specific gravity → "salinity" (SG)
- Temp → "temperature" (F)

Only include the JSON block when actual values are mentioned. Never include it for general questions.

### 2. Tank Health Analysis
You have access to the user's parameter history above. Use it to:
- Spot **trends** (dropping alk, rising nitrates, unstable pH)
- Connect **symptoms to data** ("your corals look pale" + declining calcium = likely calcium deficiency)
- **Proactively warn** when you see a dangerous pattern, even if they didn't ask
- Compare current values against ideal ranges for their specific {tank_type} tank:
{parameter_ranges}

### 3. Expert Reef Advice
You can help with:
- **Coral care**: placement, lighting needs, flow requirements, fragging, pest ID and treatment
- **Fish compatibility**: aggression, tank size requirements, dietary needs, disease diagnosis
- **Water chemistry**: the relationship between Alk/Ca/Mg, nitrogen cycle, pH buffering, trace elements
- **Equipment**: skimmer sizing, light recommendations, dosing pump setup, ATO, reactors
- **Troubleshooting**: algae outbreaks, coral RTN/STN, fish disease, parameter crashes
- **Maintenance**: water change schedules, filter media replacement, dosing calculations
- **New tank setup**: cycling, rock curing, stocking order, initial equipment

### 4. Salt-Specific Knowledge
The user uses {salt_brand}. Factor this into your advice — different salts mix to different parameter levels, and this affects dosing needs and water change strategies.

## How to Respond
- Be conversational and friendly — like a knowledgeable friend at the fish store
- Lead with the most important information first
- When parameters are concerning, explain WHY it matters and WHAT to do about it, with specific steps
- Give specific numbers and dosing amounts when possible, not vague advice
- If you notice a trend in their recent parameters, mention it proactively
- Keep responses focused — 2-4 paragraphs unless the topic requires more detail
- When logging parameters, briefly confirm what you logged
- Place the JSON extraction block (if any) as the absolute last thing in your response"""


ONBOARDING_PLAN_PROMPT = """You are ReefPilot's setup AI. The user just completed their profile questionnaire.
Analyze their setup and provide personalized advice.

Here is the user's questionnaire data:
{questionnaire_json}

Return a JSON block with this structure:
```json
{{
  "welcome_message": "A personalized 2-3 sentence welcome based on their setup",
  "parameter_targets": {{
    "salinity": {{"min": 1.024, "max": 1.026, "target": 1.025}},
    "temperature": {{"min": 76, "max": 78, "target": 77}},
    "ph": {{"min": 8.0, "max": 8.3, "target": 8.1}},
    "alkalinity": {{"min": 8, "max": 11, "target": 9}},
    "calcium": {{"min": 400, "max": 450, "target": 420}},
    "magnesium": {{"min": 1300, "max": 1400, "target": 1350}},
    "nitrate": {{"min": 2, "max": 10, "target": 5}},
    "phosphate": {{"min": 0.03, "max": 0.1, "target": 0.05}},
    "ammonia": {{"min": 0, "max": 0, "target": 0}},
    "nitrite": {{"min": 0, "max": 0, "target": 0}}
  }},
  "tips": ["tip1", "tip2", "tip3"],
  "priority_focus": "What they should focus on first"
}}
```

Personalize ALL values based on their tank type (SPS needs higher alk/cal, FOWLR is more forgiving, etc.), experience level, and goals.
Return ONLY the JSON block, no other text."""


MAINTENANCE_PLAN_PROMPT = """You are ReefPilot AI generating a personalized maintenance schedule for a reef tank owner.

## User Profile
- Experience Level: {experience_level}
- Tank Size: {tank_size} gallons
- Tank Type: {tank_type}
- Salt Brand: {salt_brand}
- Sump Size: {sump_size} gallons
- Tank Age: {tank_age_months} months
- Goals: {goals}
- Budget: ${budget_monthly}/month
- Time Available: {time_weekly_hours} hours/week
- Current Problems: {current_problems}

## Livestock
{livestock_summary}

## Equipment
{equipment_summary}

## Task
Generate a maintenance schedule as a JSON array. Each item should have:
- task_name: clear, actionable task name
- frequency: one of "daily", "weekly", "biweekly", "monthly"
- notes: brief helpful note about why/how

Tailor the schedule to their specific setup:
- Beginners get simpler, fewer tasks with more explanation
- Advanced users get more detailed optimization tasks
- SPS tanks need more frequent testing
- Consider their time budget
- Include problem-specific tasks if they have current issues

Return ONLY a JSON block like this:
```json
{{"maintenance_plan": [{{"task_name": "...", "frequency": "...", "notes": "..."}}, ...]}}
```"""


def build_system_prompt(user, livestock, recent_params, param_ranges_text):
    livestock_text = "None added yet"
    if livestock:
        items = []
        for l in livestock:
            name = l.get('common_name') or l.get('species') or 'Unknown'
            qty = l.get('quantity', 1)
            cat = l.get('category', '')
            items.append(f"- {name} ({cat}) x{qty}")
        livestock_text = "\n".join(items)

    params_text = "No readings logged yet"
    if recent_params:
        items = []
        for p in recent_params:
            items.append(f"- {p['parameter_type']}: {p['value']} {p.get('unit', '')} (logged {p['logged_at']})")
        params_text = "\n".join(items)

    return SYSTEM_PROMPT_TEMPLATE.format(
        tank_size=user.get('tank_size_gallons') or 'Unknown',
        tank_type=user.get('tank_type') or 'mixed_reef',
        salt_brand=user.get('salt_brand') or 'Unknown',
        sump_size=user.get('sump_size_gallons') or 'None',
        livestock_list=livestock_text,
        recent_params=params_text,
        parameter_ranges=param_ranges_text,
    )


def extract_params_from_response(response_text):
    """Extract the JSON parameter block from AI response text."""
    # Look for JSON block with extracted_params
    pattern = r'```json\s*(\{[^`]*"extracted_params"[^`]*\})\s*```'
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            params = data.get('extracted_params', [])
            # Validate each param
            valid = []
            for p in params:
                if p.get('type') and p.get('value') is not None:
                    # Sanity check values
                    val = float(p['value'])
                    ptype = p['type']
                    if _is_reasonable_value(ptype, val):
                        valid.append({
                            'type': ptype,
                            'value': val,
                            'unit': p.get('unit', '')
                        })
            return valid
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def clean_response(response_text):
    """Remove the JSON block from the response text shown to the user."""
    cleaned = re.sub(r'```json\s*\{[^`]*"extracted_params"[^`]*\}\s*```', '', response_text)
    return cleaned.strip()


def _is_reasonable_value(param_type, value):
    """Sanity-check extracted values to avoid logging garbage."""
    ranges = {
        'salinity': (0.5, 1.1),
        'ph': (5.0, 10.0),
        'alkalinity': (0, 30),
        'calcium': (0, 1000),
        'magnesium': (0, 3000),
        'nitrate': (0, 500),
        'nitrite': (0, 50),
        'ammonia': (0, 50),
        'phosphate': (0, 20),
        'temperature': (50, 100),
    }
    r = ranges.get(param_type)
    if r:
        return r[0] <= value <= r[1]
    return True


def format_ranges_for_prompt(ranges_dict):
    """Format parameter ranges as readable text for the system prompt."""
    lines = []
    for param, r in ranges_dict.items():
        lines.append(f"- {param}: ideal {r['min']}-{r['max']}, caution below {r['warn_low']} or above {r['warn_high']}")
    return "\n".join(lines)


def chat_with_ai(messages, system_prompt):
    """Send messages to Claude API and return the response text.
    Returns (response_text, error_message).
    """
    if not ANTHROPIC_API_KEY:
        return _demo_response(messages), None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        api_messages = []
        for m in messages:
            api_messages.append({
                "role": m['role'],
                "content": m['content']
            })

        response = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=api_messages,
        )
        return response.content[0].text, None
    except Exception as e:
        return None, str(e)


def _demo_response(messages):
    """Provide a demo response when no API key is configured."""
    last_msg = messages[-1]['content'].lower() if messages else ''

    # Check if the message contains parameter values
    param_patterns = {
        'alkalinity': r'(?:kh|alk|alkalinity|dkh)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'calcium': r'(?:ca|cal|calcium)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'magnesium': r'(?:mg|mag|magnesium)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'salinity': r'(?:salinity|sg|specific gravity)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'ph': r'(?:ph)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'nitrate': r'(?:no3|nitrate|nitrates)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'nitrite': r'(?:no2|nitrite|nitrites)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'ammonia': r'(?:nh3|nh4|ammonia)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'phosphate': r'(?:po4|phos|phosphate|phosphates)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
        'temperature': r'(?:temp|temperature)\s*(?:is|at|=|:)?\s*(\d+\.?\d*)',
    }

    units = {
        'alkalinity': 'dKH', 'calcium': 'ppm', 'magnesium': 'ppm',
        'salinity': 'SG', 'ph': '', 'nitrate': 'ppm', 'nitrite': 'ppm',
        'ammonia': 'ppm', 'phosphate': 'ppm', 'temperature': 'F',
    }

    extracted = []
    for ptype, pattern in param_patterns.items():
        match = re.search(pattern, last_msg, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            if _is_reasonable_value(ptype, val):
                extracted.append({'type': ptype, 'value': val, 'unit': units[ptype]})

    if extracted:
        param_strs = [f"{p['type'].title()}: {p['value']} {p['unit']}" for p in extracted]
        response = f"Got it! I've logged your readings: {', '.join(param_strs)}. "
        response += "Your parameters are looking good overall. Keep up the consistent testing schedule - stability is key in reef keeping!"
        response += f"\n\n```json\n{json.dumps({'extracted_params': extracted})}\n```"
        return response

    if 'hello' in last_msg or 'hi' in last_msg or 'hey' in last_msg:
        return "Hey there, fellow reefer! I'm ReefPilot AI, your reef tank assistant. You can tell me your water test results and I'll log them automatically. Try saying something like \"KH is 8.2 and calcium is 430\". I'm also here to answer any reef keeping questions you have!"

    return "I'm ReefPilot AI - your reef tank assistant! I'm running in demo mode right now (no API key configured). I can still log your water parameters - just tell me your test results like \"KH is 8, calcium 420, magnesium 1320\" and I'll track them for you. For full AI-powered advice, add your ANTHROPIC_API_KEY environment variable."
