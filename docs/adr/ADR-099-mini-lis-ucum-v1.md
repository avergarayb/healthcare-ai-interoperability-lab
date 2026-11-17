# ADR-099 — Mini LIS quantity units

## Status

Accepted for this laboratory increment. Not a terminology server and not a numeric conversion.

## Decision

Mini LIS `Observation.valueQuantity` uses the explicit map `mini-lis-ucum-v1`. The rows are `g/dL` and `mg/dL`. Each row copies the source unit text, sets `system` to `http://unitsofmeasure.org`, and sets `code` to that same text. The Mini LIS seed already stores hemoglobin as `g/dL` and GLU as `mg/dL`. `g/dL` reuses the code already published for Mini HIS. `mg/dL` uses the same identity rule. `mmol/L` is not a row.

A reference range is numeric only when the source text is `low-high`, both bounds are numeric, low is not above high, and the result unit is one of those rows. The bounds then carry the same unit, system, and code. Any other range stays text. A reversed numeric range removes the quantity system and code.

The minimizer that builds a lab-summary context omits an Observation whose unit is missing, uncoded, or whose code does not match the unit. It does not convert the number. The historical Gemini summary, receipt, and review row are not rewritten.

## Consequences

Mini HIS `mg/dL` stays uncoded. HL7 v2 still carries the original unit text and does not add a UCUM code. A stored observation that was posted as GLU `141` `mmol/L` remains that text until a new result is recorded. That old observation is not sent to a new model call.
