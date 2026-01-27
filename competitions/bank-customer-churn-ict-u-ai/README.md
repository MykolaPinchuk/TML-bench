# bank-customer-churn-ict-u-ai

This directory contains the competition spec and canonical data preparation script for the Kaggle competition `bank-customer-churn-ict-u-ai`.

## Prepare data

This creates agent-visible `public/` inputs and a private holdout under `private/` (both ignored by git):

```bash
KAGGLE_CONFIG_DIR=secrets python competitions/bank-customer-churn-ict-u-ai/prepare_competition.py --download
```

