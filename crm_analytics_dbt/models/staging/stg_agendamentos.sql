SELECT

    id,
    responsavel,
    canal,
    status,
    campanha,
    flag_agendamento,
    flag_visita,

    criação_agendamento,
    agendado_para,

    case
    when lower(flag_agendamento) = 'sim' then 1
    else 0
end as agendamento_flag,

case
    when lower(flag_visita) = 'sim' then 1
    else 0
end as visita_flag,

date(criação_agendamento) as data_agendamento,
date(agendado_para) as data_visita
 
FROM raw.agendamentos