# Start here

**1. Run the suite.** Paste this into the terminal below and press Enter:

```
docker compose up --build --exit-code-from tests
```

**2. Watch it.** A notification appears at the bottom right: click **Open in Browser**.
The page says *Starting* until the browser tests begin. If you miss the notification,
open the **Ports** tab and click the globe icon on **7900 - Live UI tests**. The app
(8000) and its inbox (8025) are listed there too.

**3. See the result.** The run ends by showing its report email, then the full report.

To see a test catch a defect, switch one on:

```
DEMO_ESP_BUGS=suppression_leak docker compose up --build --exit-code-from tests
```

The other defects are listed in `example/app/bugs.py`.
