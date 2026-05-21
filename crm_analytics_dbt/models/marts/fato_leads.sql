with leads as (

    select
        id,
        atendente,
        canal,
        empresa,
        motivo,
        data,
        convertido_flag,
        perdido_flag
    from {{ ref('stg_leads') }}

),

fato as (

select

    l.id as id_lead,

    d.id_data,
    a.id_atendente,
    c.id_canal,
    e.id_empresa,

    l.convertido_flag,
    l.perdido_flag,

    l.motivo

from leads l

left join {{ ref('dim_data') }} d
on l.data = d.data

left join {{ ref('dim_atendente') }} a
on l.atendente = a.atendente

left join {{ ref('dim_canal') }} c
on l.canal = c.canal

left join {{ ref('dim_empresa') }} e
on l.empresa = e.empresa

)

select * from fato