# Vehicle Photo Estimator

Python command-line tool and importable function. Uses the OpenAI Responses API, public photo URLs, web search, and structured JSON output. Python 3.10+; no pip dependencies.

Returns:

1. **Market rate range:** comparable accident-free clean-title retail value, with no accident-history discount. Includes sourced comparable asking prices; not confirmed sale prices.
2. **Expected repair cost:** parts and labor ranges, line items, calculated totals, assumptions, and possible hidden damage.
3. **Damage description:** visible damage, suspected damage, and inspections needed.

## Run

Copy `example_input.json` to `input.local.json`. Replace `photo_urls` with public HTTPS links that return image bytes directly (JPEG/PNG/WebP/non-animated GIF), not gallery pages, private ChatGPT links, or login-required links. The example URL is a placeholder and will not work. Update the vehicle and local shop labor rates; sample rates are assumptions, not verified quotes.

```bash
python estimate_vehicle.py input.local.json --output result.json
```

If `OPENAI_API_KEY` is unset, the CLI prompts for the key without displaying it. In an automated environment, configure `OPENAI_API_KEY` in your runtime's secret manager. No key is bundled, logged, or committed; `.env` is ignored and is not loaded automatically.

Optional model override:

```bash
python estimate_vehicle.py input.local.json --model gpt-4.1 --output result.json
```

The default is `gpt-4.1`, not an automatic latest-model alias. Your project must have access to a model supporting image input, web search, and Structured Outputs. `OPENAI_MODEL` also sets the default. API and web-search charges apply. Each run makes two API requests: research, then image analysis with structured output. Requests use `store: false`; this does not imply zero provider retention.

## Use from Python

```python
import json
from estimate_vehicle import estimate_vehicle

data = json.load(open("input.local.json"))
result = estimate_vehicle(data)  # reads OPENAI_API_KEY
# Or estimate_vehicle(data, api_key=key_from_your_secret_manager)
print(result["market_rate_range"]["range"])
print(result["expected_repair_cost"]["total"])
print(result["damage_description"]["summary"])
```

## Output shape

`market_rate_range.range`, `expected_repair_cost.parts`, `.labor`, and `.total` use `{ "low": number, "high": number }`. Currency is USD. Totals are calculated in Python, not copied from model arithmetic. Repair line items include paint materials as parts and diagnostics/calibration as labor. Taxes, auction fees, transport, and registration are excluded.

Market range is `null` if fewer than three sourced comparable listings survive provenance filtering. The model is instructed to deduplicate VINs and require evidence of clean-title, accident-free status. Source URL membership is checked against the web research response; listing prices, claims, trim, and vehicle uniqueness are still model-extracted and require human verification. This is not a licensed appraisal or a parts-ordering system.

Visible and suspected damage are kept separate. The tool does not certify frame condition, airbags, hybrid systems, or warning-light causes. Inaccessible images, incomplete/refused API responses, empty repair items, and invalid monetary ranges produce errors rather than a completed report. It cannot diagnose hidden damage from photos. Do not upload secret/customer data in URLs; use this as a backend/CLI, never expose an API key in frontend code.

## Tests

```bash
python -m unittest -v
```

Tests use mocked API responses and never spend API credits. A live run requires your key and real public image URLs. No live API test has been performed in the initial delivery.

## API references

- https://developers.openai.com/api/docs/guides/images-vision
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/guides/structured-outputs
