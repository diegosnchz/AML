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
),
flagged_transactions as (
    select
        t.transaction_id,
        t.transaction_timestamp_utc,
        t.amount_eur,
        t.sender_account_id,
        t.receiver_account_id,
        s.country as sender_country,
        r.country as receiver_country
    from {{ ref('stg_transactions') }} t
    left join {{ ref('stg_accounts') }} s
        on t.sender_account_id = s.account_id
    left join {{ ref('stg_accounts') }} r
        on t.receiver_account_id = r.account_id
    where s.country in (select country from high_risk_countries)
       or r.country in (select country from high_risk_countries)
),
account_exposure as (
    select
        sender_account_id as account_id,
        transaction_timestamp_utc,
        amount_eur,
        case
            when sender_country in (select country from high_risk_countries) then sender_country
            else receiver_country
        end as risky_country
    from flagged_transactions

    union all

    select
        receiver_account_id as account_id,
        transaction_timestamp_utc,
        amount_eur,
        case
            when receiver_country in (select country from high_risk_countries) then receiver_country
            else sender_country
        end as risky_country
    from flagged_transactions
),
ranked as (
    select
        account_id,
        max(transaction_timestamp_utc) as detected_at,
        sum(amount_eur) as amount_involved,
        count(*) as exposure_count,
        string_agg(distinct risky_country, ', ' order by risky_country) as risky_countries
    from account_exposure
    group by account_id
)

select
    md5(account_id || '|HIGH_RISK_GEOGRAPHY') as alert_id,
    account_id,
    'HIGH_RISK_GEOGRAPHY' as alert_type,
    case
        when exposure_count >= 10 then 'CRITICAL'
        when exposure_count >= 5 then 'HIGH'
        else 'MEDIUM'
    end as severity,
    detected_at,
    round(amount_involved, 2) as amount_involved,
    'Account ' || account_id || ' transacted with high-risk jurisdictions (' ||
    risky_countries || ') across ' || exposure_count ||
    ' flagged transfers, requiring enhanced due diligence.' as description
from ranked

