"""Mechanical adaptations for renamed labels and the natively observed countdown, review-only."""
from pathlib import Path

here = Path(__file__).resolve().parent
text = (here / 'round3_cases.py').read_text().replace('limits_not_observed_applied', 'inconclusive_readback')
(here / 'round3_cases_adapted.py').write_text(text)
text = (here / 'new_cases.py').read_text()
text = text.replace("1805", "1805 - row['weather_time']").replace("2205", "2205 - row['weather_time']")
text = text.replace("100 * ((30+5*i)//100+1)", "100 * ((30+5*i)//100+1) - (30+5*i)")
(here / 'new_cases_adapted.py').write_text(text)
print('Adapted only obsolete evidence label and explicit synthetic absolute deadlines to remaining seconds.')
