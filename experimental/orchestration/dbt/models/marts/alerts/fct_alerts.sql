select * from {{ ref('alert_smurfing') }}
union all
select * from {{ ref('alert_fan_out') }}
union all
select * from {{ ref('alert_fan_in') }}
union all
select * from {{ ref('alert_circular') }}
union all
select * from {{ ref('alert_layering') }}
union all
select * from {{ ref('alert_high_risk_geography') }}

