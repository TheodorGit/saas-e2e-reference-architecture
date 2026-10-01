# Start here

**1. Run the suite.** Copy this into the terminal below and press Enter:

```
docker compose up --build --exit-code-from tests
```

**2. Watch it.** When the browser tests start, the live view opens by itself in a
panel next to the terminal. If it does not, open the **Ports** tab next to the terminal
and click the globe icon on **7900 - Live UI tests**. The app (8000) and its inbox
(8025) are listed there too, if you want to look around.

**3. See the result.** The run ends by showing its report email as it arrived, then
the full report it attaches - every test, every step, a video of every browser test.

To see a test catch a defect, run it with one switched on:

```
DEMO_ESP_BUGS=suppression_leak docker compose up --build --exit-code-from tests
```

The other defects are listed in `example/app/bugs.py`.
