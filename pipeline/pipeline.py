#!/usr/env python

# In comes ... a transaction, enriched by a customer
# out goes a score from which we decide to make a policy event
#
# scam reports are for the new behaviour ... + probably training

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Transaction:
    """`transactions.parquet` — 901,286 rows (120 days)"""

    txn_id: int
    customer_id: int  # FK to CustomerMtu
    txn_ts: datetime
    amount_mxn: float
    channel: str  # spei_out, p2p_nu, card_online, card_present, cash_out, bill_payment
    counterparty_id: int
    counterparty_first_seen_flag: bool
    device_id: int
    device_new_flag: bool
    geo_state: str  # compare against CustomerMtu.home_state
    hour_of_day: int
    is_weekend: bool
    mtd_volume_before_mxn: float  # month to date volume for this customer, before this transaction
    completed_flag: bool  # whether the transaction actually went through after the policy acted

    # mtu_ratio is deliberately not in the file. Rebuilding it from mtd_volume_before_mxn
    # and the declared MTU is part of the pipeline work.


@dataclass
class CustomerMtu:
    """`customer_mtu.parquet` — 90,000 rows"""

    customer_id: int
    tenure_months: int
    income_band: str
    mtu_declared_mxn: float  # the ceiling declared at onboarding, what the current policy uses
    mtu_observed_p95_mxn: float  # what the customer actually transacts, from history
    avg_ticket_90d_mxn: float  # the customer's normal transaction size
    prior_scam_report_flag: bool
    risk_segment: str  # low, medium, high
    home_state: str


@dataclass
class PolicyEvent:
    """`policy_events.parquet` — 37,925 rows (only transactions the policy acted on)"""

    event_id: int
    txn_id: int  # FK
    rule_id: str  # P-01 to P-05
    rule_description: str
    action_taken: str  # delay, scam_alert, or none
    policy_holdout_flag: bool
    mtu_breach_flag: bool  # the month volume went over the declared ceiling
    customer_proceeded: bool  # for scam_alert, whether the customer went ahead anyway
    bypass_requested: bool  # for delay, whether Ops was contacted
    bypass_granted: bool  # for delay, what Ops decided
    ops_contact_flag: bool  # an Ops contact happened, which has a real cost
    minutes_blocked: int  # how long the customer was unable to transact


@dataclass
class ScamReport:
    """`scam_reports.parquet` — 4,272 rows"""

    report_id: int
    txn_id: int  # FK
    reported_ts: datetime  # reports arrive with a lag, sometimes days later
    confirmed_scam: bool  # main label, after investigation
    loss_amount_mxn: float  # 0 when not confirmed
    report_channel: str  # app, phone, chat
