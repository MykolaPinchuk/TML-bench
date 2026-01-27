# playground-series-s5e10

Competition scaffold for the Kaggle competition `playground-series-s5e10`.

## Prepare data

This creates agent-visible `public/` inputs and a private holdout under `private/` (both ignored by git):

```bash
KAGGLE_CONFIG_DIR=secrets python competitions/playground-series-s5e10/prepare_competition.py --download
```

