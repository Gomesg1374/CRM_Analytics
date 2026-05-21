with datas as (

    select distinct
        date(data_criação) as data
    from {{ ref('stg_leads') }}

),

dim_data as (

select

    cast(strftime('%Y%m%d', data) as bigint) as id_data,

    data,

    extract(year from data) as ano,

    extract(month from data) as mes,

    case extract(month from data)
        when 1 then 'Janeiro'
        when 2 then 'Fevereiro'
        when 3 then 'Março'
        when 4 then 'Abril'
        when 5 then 'Maio'
        when 6 then 'Junho'
        when 7 then 'Julho'
        when 8 then 'Agosto'
        when 9 then 'Setembro'
        when 10 then 'Outubro'
        when 11 then 'Novembro'
        when 12 then 'Dezembro'
    end as mes_nome,

    extract(day from data) as dia,

    extract(quarter from data) as trimestre,

    extract(dow from data) as dia_semana_num,

    case extract(dow from data)
        when 0 then 'Domingo'
        when 1 then 'Segunda'
        when 2 then 'Terça'
        when 3 then 'Quarta'
        when 4 then 'Quinta'
        when 5 then 'Sexta'
        when 6 then 'Sábado'
    end as dia_semana_nome,

    extract(week from data) as semana_ano,

    case 
        when extract(dow from data) in (0,6) then 1
        else 0
    end as fim_de_semana

from datas

)

select * from dim_data