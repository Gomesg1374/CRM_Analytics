select
row_number() over() as id_empresa,
empresa
from (
    select distinct empresa
    from {{ ref('stg_leads') }}
)