select

id,
cliente,
telefone,
canal,
atendente,
empresa,
conversão,
motivo,

data_criação,
ultima_integração,

case
    when lower(conversão) = 'ganho' then 1
    else 0
end as convertido_flag,

case
    when lower(conversão) = 'perdido' then 1
    else 0
end as perdido_flag,

date(data_criação) as data

from raw.leads