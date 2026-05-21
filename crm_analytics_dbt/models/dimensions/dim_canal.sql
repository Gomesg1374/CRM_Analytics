select
row_number() over() as id_canal,
canal
from (
    select distinct canal
    from {{ ref('stg_leads') }}
)