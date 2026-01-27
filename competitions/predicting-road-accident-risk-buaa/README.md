# predicting-road-accident-risk-buaa

Competition scaffold for the Kaggle competition `predicting-road-accident-risk-buaa`.

## Prepare data

This creates agent-visible `public/` inputs and a private holdout under `private/` (both ignored by git):

```bash
KAGGLE_CONFIG_DIR=secrets python competitions/predicting-road-accident-risk-buaa/prepare_competition.py --download
```

If you get a `403 Forbidden`, open the competition page in a browser, accept the rules / enter the competition, then rerun.

