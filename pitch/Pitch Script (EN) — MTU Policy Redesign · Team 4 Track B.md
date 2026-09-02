# **Pitch Script — MTU Policy Redesign**

**Team 4 · Track B** · 22 slides · target runtime **12 minutes**  
*Written to be spoken. Short sentences on purpose. \[PAUSE\] means actually stop talking for a beat — the silence does the work.*

## ---

**Before you start**

> * **Update slide 22\.** Guardrail 2 is no longer "not yet quantified" — you measured it. New numbers below.  
> * **The three moments that carry the whole pitch:** slide 6 (lift below 1.0), slide 16 (the three zones), slide 20 (the three numbers). Slow down on those. Everything else can move fast.  
> * **If you are running long,** cut slide 11 (it repeats slide 8\) and shorten slide 15 to one sentence.

# ---

**SLIDE 1 — Title (15s)**

"Good morning. Team 4, Track B.  
Our headline in one line: **the current MTU policy blocks customers who are *safer* than average — and we can prove it with the challenge's own metric.**  
What we built prevents sixteen times more loss while cutting blocked hours in half."  
*\[Move on immediately. Do not read the three stat boxes — the audience already sees them.\]*

# ---

**SLIDE 2 — Context (35s)**

"Thirty seconds of setup.  
MTU is the **monthly transaction ceiling each customer declares**. It exists because of Article 287 Bis — it's a **regulatory** control, designed to cap how much a customer can lose.  
Today, five rules read how much of that ceiling a payment consumes. The closer you are to the ceiling, the harsher the action: a warning, then a delay, then a twelve-hour block.  
We had twenty-seven weeks of data. Nine hundred thousand transactions. Two thousand eight hundred and seventy-two confirmed scams.  
The ask: judge that policy, and propose a better one. Scored on **loss avoided per hour of blocking imposed on a legitimate customer**."

# ---

**SLIDE 3 — Methodology (20s)**

"Five steps, straight from the brief. Diagnose the policy rule by rule. Build a score. Compare against the incumbent and against an MTU-only baseline. Set justified thresholds. And find a pattern the current policy can't see.  
Two guardrails: **blocked hours on legitimate customers**, and **MTU monitoring compliance**. We'll come back to both at the end."

# ---

**SLIDE 4 — Phase 1 divider (5s)**

"So — the diagnosis."

# ---

**SLIDE 5 — Baselines reproduced (30s)**

"Before proposing anything, we had to earn the right to be believed.  
The brief published three baseline numbers. We rebuilt the pipeline from the raw parquets and reproduced all three.  
Four point two percent of transactions receive an action — we got four point two one. Ninety-nine point eight percent of delays are false positives — we got ninety-nine point eight three. Two hundred thirty-four thousand, eight hundred thirty-one hours of blocking — **exact match**.  
\[PAUSE\]  
Every number after this rests on that."

# ---

**SLIDE 6 — The harshest action goes to the safest customers (75s) ★**

*\[This is your slide. Slow down.\]*  
"Now the finding.  
The base rate of fraud here is **three in a thousand**. So for every rule we asked one question: how many times better than random is it at finding fraud? That's the lift.  
P-04 — new counterparty plus a large amount — is **3.9 times** better than random. P-02 and P-03, around two.  
Those three rules only send a warning.  
\[PAUSE\]  
Now the two rules that impose the **twelve-hour block**.  
P-01, the MTU breach: **0.62**. P-05, night-time cash-outs: **0.41**.  
\[PAUSE — let the red bars sit there\]  
**Both are below one.** That means a transaction flagged by these rules is *less* likely to be fraud than a transaction picked completely at random. And it's the one we block for twelve hours.  
We are applying the harshest action in the system to a population that is **safer than average**.  
The reason is structural: **action severity is ordered by how much of the ceiling you consumed — not by how likely you are to be defrauded.**  
One number to make it concrete. P-05 alone burns forty-seven thousand blocked hours — twenty percent of all friction in the system — to touch four thousand eight hundred pesos of loss. That's **ten centavos per hour** of customer friction."

# ---

**SLIDE 7 — Phase 2 divider (5s)**

"Which raises the obvious question: if not MTU, then what?"

# ---

**SLIDE 8 — MTU is a compliance control (40s)**

"MTU was never a fraud signal. It exists to satisfy a regulation. It answers *'is this customer overspending their declared ceiling?'* — which is not the same question as *'is this a scam?'*.  
So we measured every available signal against the same base rate.  
**New device: ten times** better than random. Present in thirty-eight percent of scams, under four percent of legitimate transactions.  
**New counterparty: six times.** Sixty-eight percent versus eleven. And it makes intuitive sense — **nobody gets scammed paying their usual landlord**.  
MTU ratio? One point five.  
And geo mismatch carries **no signal at all** — it actually points slightly the wrong way, so we dropped it. Features selected on evidence, not on availability."

# ---

**SLIDE 9 — Three uncomfortable truths (60s)**

"Three things we found that changed how we *measured* everything.  
**One.** The block doesn't last twelve hours. It lasts **nine** — because twenty-four percent of customers request and get an early release.  
**Two.** The actions don't work at a hundred percent. Seventy-nine out of a hundred warned customers **proceed anyway**. So a warning deters twenty-one percent, and a block holds seventy-six. Every loss figure we report is multiplied by those.  
**Three** — and this one is uncomfortable. We checked, and **every single confirmed scam has completed\_flag equal to true**. The money left. So what the policy calls 'loss captured' is **loss that happened**, on transactions where the policy fired and failed.  
Which creates a real problem: **prevented fraud is invisible.** If a block actually stops a scam, there's no report, no label, no row. You cannot measure success by counting positives.  
So we used the **holdout group** — two thousand three hundred transactions that triggered a rule but got no action. Their scam rate is 0.517 percent against 0.345 in the treated group. That's roughly a third fewer scams: about sixty-one scams, four hundred ten thousand pesos.  
Full honesty: that rests on **twelve events**. The confidence interval is wide. It's directional, not conclusive — and we'd rather tell you that than quote it as fact."

# ---

**SLIDE 10 — Phase 3 divider (5s)**

"So we built a model."

# ---

**SLIDE 11 — Behavioural novelty (25s)**

"To restate the point that drives everything downstream: the strongest signals in this dataset are all about **novelty**. New counterparty, new device, unusual ticket size.  
MTU — the variable the entire policy is built on — is one of the **weakest** signals available."  
*\[If running long, skip this slide entirely — slide 8 already made the point.\]*

# ---

**SLIDE 12 — The model (55s)**

"Gradient boosting. Three hundred trees, depth four, class-weighted 456 to one.  
It predicts the probability that a transaction becomes a confirmed scam, using **only information available at the moment of the transaction**.  
Why it beats a rule set: it finds **combinations nobody programmed**. 'New counterparty' on its own gives you one point nine percent precision across a hundred thousand transactions — too broad to act on. Cross it with 'new device' and you get roughly **sixteen percent precision** over four and a half thousand. The model does that automatically, across dozens of combinations at once.  
Test AUC-ROC: **0.9458**. AUC-PR: **0.3939** — and before anyone asks, the random baseline for PR-AUC is the prevalence itself, 0.0079. So we're **fifty times above random**.  
And the punchline for this slide: **mtu\_ratio ranks sixth** in feature importance. Behind new counterparty, new device, tenure and ticket ratio.  
Critically — **we trained only on weeks up to twenty-three**. A temporal split, not a random one. That matters, and I'll show you why in a moment."

# ---

**SLIDE 13 (20s)**

*\[This slide is an image with no notes — I don't know what it shows. If it's the feature importance chart, say:\]*  
"Here's the full importance ranking. Notice the top of the list is behavioural, and MTU sits down here."  
*\[If it's something else, one sentence naming what it shows and why it's there is enough.\]*

# ---

**SLIDE 14 — Phase 4 divider (5s)**

"Now — a score isn't a policy. Someone still has to decide what to do with the number."

# ---

**SLIDE 15 — Four changes (25s)**

"We changed four things about the decision itself.  
We decide on **expected loss**, not probability. We optimise **net value**, not a ratio. We constrained the search with guardrails. And we **calibrated the score** before using it.  
Let me show you the first and the last — they're the ones that changed the outcome."

# ---

**SLIDE 16 — The three zones (65s) ★**

"The rule is one line: **risk in pesos equals calibrated score times transaction amount.**  
Below six pesos of risk, we allow. Between six and thirty, we warn. Above thirty, we delay.  
\[PAUSE\]  
Here's the argument. **A five percent chance of fraud on a two-hundred-peso transfer does not justify blocking someone for nine hours. The same five percent on thirty thousand pesos obviously does.**  
The current policy is completely blind to the amount. P-05 blocks every night-time cash-out — whether it's two hundred pesos or twenty thousand.  
And this design gives us something better than a good model. Because the score can never exceed one, **no transaction below thirty pesos can ever be delayed** — no matter how suspicious it looks. The 'two hundred pesos blocked for twelve hours' scenario doesn't disappear because we trust the model. It disappears **by construction**.  
One more thing on this slide, and it's my favourite result of the whole project. We derived the economically optimal delay threshold from first principles — cost of blocking, effectiveness of each action, nothing else. That gives **one hundred ninety-seven pesos** of expected loss. Adjusted for the calibration gap, about forty-five in our units.  
The grid search, running completely independently on the data, found **thirty**.  
**Economic theory and empirical optimisation converged on the same threshold from opposite directions.**"

# ---

**SLIDE 17 — Two mistakes (40s)**

"Two mistakes we made, because I think they're more interesting than the things that went right.  
**First: we optimised the North Star directly.** Seemed obvious — it's the metric we're scored on. But a ratio can always be improved by shrinking its denominator. The optimiser figured out that warnings are nearly free and ended up **warning eighty-eight percent of all transactions** — with a warn-bucket precision *below* the base rate. Exactly the pathology we'd just criticised in P-05.  
The fix: maximise **net value in pesos**. The North Star is a reporting metric. It is not an objective function.  
**Second: the score wasn't a probability.** The class weighting inflates it and compresses the top end — a 0.99 reads as only 1.6 times a 0.62, when the true risk ratio is about fifty. Multiplied by amount, **the amount was dominating the decision**.  
The fix was a calibration correction. Net value up seventeen percent, blocked hours down **fifty-five percent**, and delay precision more than doubled."

# ---

**SLIDE 18 — Phase 5 divider (5s)**

"So — results."

# ---

**SLIDE 19 — Results (55s)**

"Three policies. Ours, the incumbent, and an MTU-only baseline. **Same one hundred fifty-eight thousand test transactions, same effectiveness assumptions.** No apples to oranges.  
Scams caught: **1,077** versus 86\. Loss prevented: **2.9 million** versus 176 thousand — sixteen point seven times. North Star: **thirty-four point seven times** better.  
And blocked hours: **down fifty-two percent**.  
\[PAUSE\]  
I want to be precise about what that means, because it's the part I'd push back on if I were you.  
**This is not a trade-off.** We delay *half* as many transactions as the incumbent and still catch thirty times more scams. It's not that we're buying detection with friction — we're **reallocating the same friction budget** toward the transactions where the money at risk actually justifies it.  
One more thing on this slide. Both the current policy and the MTU-only baseline come out with **negative net value**. The friction they impose costs more than the fraud they prevent."

# ---

**SLIDE 20 — The three numbers (40s) ★**

*\[Slow down. One number at a time. Don't rush the close.\]*  
"If you remember three numbers from this presentation:  
**One hundred thirty pesos and forty-three centavos** of loss prevented per hour of blocking, against three seventy-six today. That's the challenge's own North Star — **thirty-five times better**.  
\[PAUSE\]  
**Minus three hundred eighty-four thousand pesos.** That's the net value of the policy running in production right now. Not *improvable* — **negative**. It destroys value.  
\[PAUSE\]  
And **twenty-two thousand blocked hours** against forty-six thousand. The guardrail the brief named explicitly doesn't just survive — **it improves by half**.  
And all of this is measured on a period the model **had never seen during training**."

# ---

**SLIDE 21 — The pattern (60s)**

"Which brings me to the last finding.  
Four weeks out of roughly twenty hold **forty-four percent of all confirmed scams and fifty-nine percent of all losses**.  
But volume isn't the interesting part. Look at what changed **inside** those scams.  
New counterparty goes from fifty percent to **eighty-seven**. New device from thirty-two to forty-five. Average hour shifts five hours later, into the evening.  
\[PAUSE\]  
**That's not more of the same fraud. That's a different operation.**  
And here's why the current policy can't see it: its rules are **static thresholds on accumulated monthly volume**. Not one of them looks at counterparty novelty, or device, or time of day. It isn't badly tuned — **it has no variable capable of seeing this**. On these exact weeks it catches six point nine percent.  
Our model catches **eighty-six**. And not because it saw the outbreak — it was trained only on the weeks before. It simply already gave the highest weight to the two variables the outbreak went on to exploit. **It was looking at the right things.**  
One bonus. Because the model was calibrated on the old regime, it expects 0.18 percent and reality delivered 0.79. That gap **is** the regime change — which makes it a **free early-warning alarm**. No new labels, no retraining, no analyst review. The incumbent policy has nothing like it."

# ---

**SLIDE 22 — Guardrails and what's next (50s)**

*\[UPDATE THIS SLIDE FIRST — see the note below.\]*  
"Let me close on the two guardrails, and on what we *didn't* solve.  
**Guardrail one, blocked hours: it improves.** Forty-six thousand down to twenty-two. Half as many legitimate customers delayed.  
**Guardrail two, MTU compliance.** We measured it, and it produced a finding we didn't expect.  
We split MTU into its two bands. **Breaching the ceiling has a lift of 0.65 — below random. Approaching the ceiling has a lift of 3.11 — genuinely predictive.**  
So the policy is **exactly inverted**: it applies the twelve-hour block to the band that *doesn't* predict fraud, and a warning to the band that does. P-02 is defensible. P-01 is not.  
On compliance itself: **a hundred percent of breaches continue to be logged and reported** under Article 287 Bis. What changes is that a breach stops automatically triggering the fraud block. We still act on twenty-nine percent of them — the ones with real risk. The other seventy-one percent are legitimate customers spending their own money, in a band that is **safer than average**.  
The open question for Product and Legal: is blocking on breach a legal obligation, or a discretionary choice? If it's an obligation, our two-layer architecture already handles it.  
And three things we'd do next: **mule detection** — counterparty\_id is completely untouched and shared destinations is the obvious hypothesis for that outbreak. **Warning redesign** — seventy-nine percent ignore it today, and that's a Product lever no model can pull. And **pinning down the cost parameters** — the value of one blocked hour is still an assumption, and every threshold derives from it.  
Thank you."

# ---

**Slide 22 — what to change**

Replace the Guardrail 2 card. It currently reads "preserved, not yet quantified". Suggested replacement:  
**Guardrail 2 — MTU compliance ✓ measured**

| Band | Txns | Fraud rate | Lift | Today | New coverage |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Breach (≥ 1.00) | 4,289 | 0.51% | **0.65x** | Delay 12h | 29.1% |
| Near ceiling (0.85–1.00) | 2,277 | 2.46% | **3.11x** | Warning | 35.1% |

Caption: *100% of breaches remain logged under Article 287 Bis. The policy is inverted: the harshest action goes to the band that does not predict fraud.*

# ---

**Delivery notes**

> * **Three slides carry the pitch:** 6, 16, 20\. Everything else can be delivered at pace. On those three, slow down and use the pauses.  
> * **Say numbers as words** for the headline figures — "thirty-four point seven times" lands harder than reading "34.7x" off the screen.  
> * **Never read a slide.** The audience reads faster than you talk. Say the thing the slide *doesn't* say.  
> * **Name your limits before they're asked.** The twelve-event holdout, the conservative peso figures, the open legal question. Volunteering weaknesses is the strongest credibility signal available to you.  
> * **If you go blank,** come back to the five-act spine: the policy doesn't work → it measures the wrong thing → here are the right signals → we redesigned the decision → less friction and more fraud caught.