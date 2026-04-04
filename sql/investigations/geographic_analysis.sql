/*
Purpose:
Measure transaction corridors by country pair and flag routes that touch a hardcoded high-risk jurisdiction watchlist.

Why it matters:
Cross-border concentration, especially involving monitored or high-risk jurisdictions, is a key AML risk indicator and helps analysts focus on suspicious geographies and payment corridors.
*/

with high_risk_countries as (
    select country
    from (
        values
            ('IRAN'),
            ('DPRK'),
            ('MYANMAR'),
            ('SYRIA'),
            ('YEMEN'),
            ('HAITI'),
            ('SOUTH SUDAN'),
            ('NIGERIA'),
            ('VENEZUELA'),
            ('CAMEROON'),
            ('CROATIA'),
            ('KENYA'),
            ('NAMIBIA'),
            ('VIETNAM'),
            ('SOUTH AFRICA')
    ) as watchlist(country)
)

select
    sender.country as sender_country,
    receiver.country as receiver_country,
    count(*) as txn_count,
    round(sum(t.amount_eur), 2) as total_amount_eur,
    round(avg(t.amount_eur), 2) as avg_amount_eur,
    count(*) filter (where t.is_laundering = 1) as labeled_laundering_txn_count,
    case
        when sender.country in (select country from high_risk_countries)
          or receiver.country in (select country from high_risk_countries)
        then 'HIGH_RISK_CORRIDOR'
        else 'STANDARD_CORRIDOR'
    end as corridor_flag
from staging.stg_transactions t
left join staging.stg_accounts sender
    on t.sender_account_id = sender.account_id
left join staging.stg_accounts receiver
    on t.receiver_account_id = receiver.account_id
group by 1, 2, 7
order by corridor_flag desc, total_amount_eur desc, txn_count desc

