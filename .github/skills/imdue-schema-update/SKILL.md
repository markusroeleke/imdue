---
name: imdue-schema-update
description: 'Update the structured output schema for the Immobilien Due Diligence app. Use when: adding or removing fields, changing enum values, adjusting nullable types, or keeping schema.py, the skills spec, and report.html in sync after a schema change.'
argument-hint: 'Describe the field change, e.g. "add purchase_price_eur to kpis"'
---

# Immobilien Due Diligence — Schema Update

## When to Use
- Adding a new output field (e.g. a new KPI or risk category)
- Removing or renaming an existing field
- Changing an `enum` list (e.g. new severity level or recommendation option)
- Making a required field nullable (or vice versa)
- Syncing code after spec changes in the documentation

---

## Files That Must Stay in Sync

Every schema change touches **all three** of the following files:

| File | What to Update |
| :--- | :--- |
| [src/schema.py](../../src/schema.py) | Python dict — source of truth sent to Manus API |
| [doc/Due_Diligence_Agent_Skills_Spezifikation.md](../../doc/Due_Diligence_Agent_Skills_Spezifikation.md) | JSON schema block in section 5 |
| [src/templates/report.html](../../src/templates/report.html) | Jinja2 template rendering the new field |

---

## Procedure

### Step 1 — Update `src/schema.py`

This is the canonical definition. All other files follow from it.

**Rules (enforced by Manus API):**
- `"additionalProperties": False` on every object
- Every property listed in `"required"`
- Optional fields use nullable types: `{"type": ["string", "null"]}`

Example — adding a field to `kpis`:
```python
"kpis": {
    "type": "object",
    "properties": {
        # ... existing fields ...
        "purchase_price_eur": {"type": ["number", "null"]},  # NEW
    },
    "required": [
        # ... existing required list + new field ...
        "purchase_price_eur",
    ],
    "additionalProperties": False,
},
```

### Step 2 — Update the JSON block in the spec doc

Open [doc/Due_Diligence_Agent_Skills_Spezifikation.md](../../doc/Due_Diligence_Agent_Skills_Spezifikation.md), section **5. Das Structured Output Schema**, and apply the same change to the JSON code block so it mirrors `schema.py`.

### Step 3 — Update `src/templates/report.html`

Add a rendering block for the new field in the appropriate section of the HTML template. Use the existing Jinja2 patterns:

```html
<!-- For a nullable number in kpis: -->
{% if k.purchase_price_eur is not none %}
  <div class="kpi-value">{{ "%.0f"|format(k.purchase_price_eur) }} €</div>
{% else %}
  <div class="kpi-na">k. A.</div>
{% endif %}
```

For array fields:
```html
{% for item in data.new_field %}
  <li>{{ item }}</li>
{% endfor %}
```

### Step 4 — Update the `src/manus_client.py` prompt (if needed)

If the new field requires the KI to explicitly compute or look for something, add a hint to the prompt string in `create_analysis_task`.

### Step 5 — Verify

Run the app and trigger a test analysis:
```bash
chainlit run src/app.py -w
```
- Confirm no `Schema-Fehler` appears in the chat
- Confirm the new field renders correctly in the PDF

---

## Validation Checklist

- [ ] `schema.py`: new field in `properties` dict
- [ ] `schema.py`: new field in `required` list
- [ ] `schema.py`: nullable if the data may be absent in documents
- [ ] `schema.py`: nested object has `"additionalProperties": False`
- [ ] Spec doc JSON block matches `schema.py` exactly
- [ ] `report.html` renders the new field (with `k. A.` fallback for nullables)
- [ ] Test analysis completes without `Schema-Fehler`

---

## Common Mistakes

| Mistake | Effect | Fix |
| :--- | :--- | :--- |
| Field in `properties` but not in `required` | Manus may skip the field | Add to `required` |
| Missing `"additionalProperties": False` on nested object | Schema validation error from Manus | Add the key |
| Non-nullable `number` when data may be absent | Manus returns null → Python crash | Use `["number", "null"]` |
| Spec doc and `schema.py` out of sync | Developer confusion | Update both in the same PR |
