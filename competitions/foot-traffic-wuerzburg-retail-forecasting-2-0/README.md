# foot-traffic-wuerzburg-retail-forecasting-2-0

Competition scaffold for `foot-traffic-wuerzburg-retail-forecasting-2-0`.

## Prepare data

Creates agent-visible `public/` and private `private/` holdout (both ignored by git):

```bash
KAGGLE_CONFIG_DIR=secrets python competitions/foot-traffic-wuerzburg-retail-forecasting-2-0/prepare_competition.py --download
```

