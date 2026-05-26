const API_BASE = "https://climate.expansao-ai.com.br"


async function carregarStatus(){

    try{

        const response =
        await fetch(
            `${API_BASE}/climate/status`
        )

        const dados =
        await response.json()

        document
        .getElementById("oni")
        .innerText =
        dados.oni.toFixed(2)

        document
        .getElementById("status")
        .innerText =
        dados.classificacao

        document
        .getElementById("nino34")
        .innerText =
        dados.nino34.toFixed(2)

        document
        .getElementById("fase")
        .innerText =
        dados.fase

    }

    catch{

        mostrarErro(
            "Erro carregando status"
        )

    }

}


async function carregarHistorico(){

    try{

        const response =
        await fetch(
            `${API_BASE}/climate/history`
        )

        const dados =
        await response.json()

        montarGrafico(
            dados
        )

    }

    catch{

        mostrarErro(
            "Erro histórico NOAA"
        )

    }

}


async function carregarInsight(){

    try{

        const response =
        await fetch(
            `${API_BASE}/climate/analysis`
        )

        const dados =
        await response.json()

        document
        .getElementById(
            "analysis"
        )
        .innerText =
        dados.analysis

    }

    catch{

        mostrarErro(
            "Erro análise"
        )

    }

}


async function carregarTendencia(){

    try{

        const response =
        await fetch(
            `${API_BASE}/climate/trend`
        )

        const dados =
        await response.json()

        let simbolo="➡"

        if(
            dados.tendencia==="SUBINDO"
        )
        simbolo="⬆"

        if(
            dados.tendencia==="CAINDO"
        )
        simbolo="⬇"

        document
        .getElementById(
            "tendencia"
        )
        .innerText=

        simbolo+

        " "+

        dados.tendencia

        document
        .getElementById(
            "variacao"
        )
        .innerText=

        "Δ "+

        dados.variacao.toFixed(2)

    }

    catch{

        mostrarErro(
            "Erro tendência"
        )

    }

}


async function carregarAtualizacao(){

    try{

        const response =
        await fetch(
            `${API_BASE}/climate/update`
        )

        const dados =
        await response.json()

        document
        .getElementById(
            "ultimaAtualizacao"
        )
        .innerText=

        dados.ultima_atualizacao

        document
        .getElementById(
            "fonte"
        )
        .innerText=

        dados.fonte

    }

    catch{

        mostrarErro(
            "Erro atualização NOAA"
        )

    }

}


async function carregarAlertas(){

    try{

        const response =
        await fetch(
            `${API_BASE}/api/climate/alerts`
        )

        const dados =
        await response.json()

        renderizarAlertas(
            dados.items
        )

    }

    catch{

        mostrarErro(
            "Erro alertas operacionais"
        )

    }

}


function renderizarAlertas(alertas){

    const container =
    document.getElementById(
        "climate-alerts"
    )

    if(!container){
        return
    }

    container.innerHTML = ""

    if(!alertas || alertas.length === 0){

        container.innerHTML =
        "<p>Nenhum alerta operacional ativo.</p>"

        return

    }

    alertas.forEach(
        alerta => {

            const card =
            document.createElement(
                "div"
            )

            card.className =
            "alert-card " +
            alerta.severity.toLowerCase()

            const titleEl = document.createElement("div")
            titleEl.className = "alert-title"
            titleEl.textContent = alerta.title

            const messageEl = document.createElement("div")
            messageEl.className = "alert-message"
            messageEl.textContent = alerta.message

            const sourceEl = document.createElement("div")
            sourceEl.className = "alert-source"
            sourceEl.textContent = "Fonte: " + alerta.source

            card.appendChild(titleEl)
            card.appendChild(messageEl)
            card.appendChild(sourceEl)

            container.appendChild(
                card
            )

        }
    )

}


function montarGrafico(dados){

    const labels=
    dados.map(
        x=>x.periodo
    )

    const valores=
    dados.map(
        x=>x.oni
    )

    const ctx=

    document

    .getElementById(

        "oniChart"

    )

    new Chart(

        ctx,

        {

            type:"line",

            data:{

                labels,

                datasets:[

                {

                    label:"ONI",

                    data:valores,

                    borderColor:"#5EC8F8",

                    borderWidth:3,

                    tension:.35,

                    pointRadius:5,

                    pointBackgroundColor:

                    valores.map(

                    x=>{

                    if(x>=0.5)

                    return"#FF5C5C"

                    if(x<=-0.5)

                    return"#4DA6FF"

                    return"#C9D2DD"

                    }

                    )

                },

                {

                    label:

                    "El Niño",

                    data:

                    labels.map(
                    ()=>0.5
                    ),

                    borderDash:[5,5],

                    borderColor:"#FF6464",

                    pointRadius:0

                },

                {

                    label:

                    "La Niña",

                    data:

                    labels.map(
                    ()=>-0.5
                    ),

                    borderDash:[5,5],

                    borderColor:"#4DA6FF",

                    pointRadius:0

                }

                ]

            }

        }

    )

}


function mostrarErro(msg){

    document
    .getElementById(
        "erro"
    )
    .innerText=
    msg

}


carregarStatus()

carregarHistorico()

carregarInsight()

carregarTendencia()

carregarAtualizacao()

carregarAlertas()