with agendamentos as (

    select

        id,
        responsavel,
        canal,
        status,
        campanha,
        data_agendamento,
        data_visita,
        agendamento_flag,
        visita_flag

      --case
      --      when lower(flag_agendamento) = 'sim' then 1
      --      else 0
      --  end as flag_agendamento,

      --  case
      --      when lower(flag_visita) = 'sim' then 1
      --      else 0
      --  end as flag_visita

    from {{ ref('stg_agendamentos') }}

),

fato as (

select

    a.id as id_agendamento,

    da.id_atendente,
    dc.id_canal,

    --a.data_agendamento as dataagendamento,
    --a.data_visita as datavisita,

    d1.id_data as id_data_agendamento,
    d2.id_data as id_data_visita,

    a.agendamento_flag,
    a.visita_flag,

    a.status,
    a.campanha

from agendamentos a

left join {{ ref('dim_atendente') }} da
on a.responsavel = da.atendente

left join {{ ref('dim_canal') }} dc
on a.canal = dc.canal

left join {{ ref('dim_data') }} d1
on a.data_agendamento = d1.data
left join {{ ref('dim_data') }} d2
on a.data_visita = d2.data

)

select * from fato