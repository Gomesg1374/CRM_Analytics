select
row_number() over() as id_atendente,
atendente
from (
    select distinct atendente
    from {{ ref('stg_leads') }}
)