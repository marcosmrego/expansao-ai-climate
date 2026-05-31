async function montarMapaClimatico() {
    const svgEl = document.getElementById("climateMap")
    if (!svgEl || typeof d3 === "undefined" || typeof topojson === "undefined") return

    // 1. Fetch data in parallel
    const [rOni, rArctic, rAntarctic, rIod, rMjo] = await Promise.allSettled([
        fetch(`${API_BASE}/climate/history`),
        fetch(`${API_BASE}/climate/arctic_ice/history`),
        fetch(`${API_BASE}/climate/antarctic_ice/history`),
        fetch(`${API_BASE}/climate/iod/history`),
        fetch(`${API_BASE}/climate/mjo`),
    ])
    const jj = async r => r.status === "fulfilled" && r.value.ok ? r.value.json() : []
    const [oniData, arcticData, antarcticData, iodData, mjoData] = await Promise.all([
        jj(rOni), jj(rArctic), jj(rAntarctic), jj(rIod), jj(rMjo)
    ])
    if (!oniData.length) return

    // 2. Build monthly ice averages from daily data
    function monthlyAvg(daily) {
        const acc = {}
        daily.forEach(d => {
            const key = d.data_referencia.slice(0, 7)
            if (!acc[key]) acc[key] = []
            acc[key].push(d.extent_mkm2)
        })
        return Object.fromEntries(Object.entries(acc).map(([k, v]) => [k, v.reduce((a, b) => a + b, 0) / v.length]))
    }
    const arcticByMonth    = monthlyAvg(arcticData)
    const antarcticByMonth = monthlyAvg(antarcticData)
    const iodByMonth       = Object.fromEntries((iodData||[]).map(d => [d.data_referencia?.slice(0,7), d.value]))

    // 3. Build 12-month dataset (most recent 12 months from ONI)
    const frames = oniData.slice(-12).map(o => ({
        period: o.periodo,
        oni: o.oni,
        classificacao: o.classificacao,
        arctic: arcticByMonth[o.periodo] ?? 11.0,
        antarctic: antarcticByMonth[o.periodo] ?? 10.0,
        iod: iodByMonth[o.periodo] ?? 0,
    }))

    // MJO phase → equatorial longitude center
    const MJO_LON = { 1: 55, 2: 75, 3: 95, 4: 115, 5: 140, 6: 165, 7: -160, 8: -100 }

    // 4. Extent → geo radius (spherical cap formula: area = 2πR²(1−sinφ))
    const R2 = 255.03  // 2πR² in Mkm²
    function extentToRadius(extMkm2, pole) {
        const sinPhi = 1 - Math.min(extMkm2, R2 * 0.95) / R2
        const phiDeg = Math.asin(Math.max(0, Math.min(1, sinPhi))) * 180 / Math.PI
        return 90 - phiDeg + 2  // +2° buffer for visual clarity
    }

    // 5. Color scales
    // Paleta mais vibrante e saturada
    const oniColor = d3.scaleLinear()
        .domain([-2, -1, -0.5, 0, 0.5, 1, 2])
        .range(["#00B0FF","#29B6F6","#B3E5FC","#90A4AE","#FF8A65","#FF3D00","#B71C1C"])
        .clamp(true)
    const iodColor = d3.scaleLinear()
        .domain([-1, 0, 1])
        .range(["#00E676","#546A84","#FFD740"])
        .clamp(true)

    // 6. Setup SVG
    const W = svgEl.parentElement.clientWidth || 800
    const H = Math.round(W * 0.52)
    svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`)

    const projection = d3.geoNaturalEarth1()
        .scale(W / 6.28)
        .translate([W / 2, H / 2])
    const path = d3.geoPath().projection(projection)

    const svg = d3.select(svgEl)
    svg.selectAll("*").remove()

    // Definições SVG: gradientes radiais para gelo polar
    const defs = svg.append("defs")

    // Gradiente ártico: branco → ciano → transparente
    const gradArctic = defs.append("radialGradient")
        .attr("id", "gradArctic").attr("cx","50%").attr("cy","20%")
        .attr("r","70%")
    gradArctic.append("stop").attr("offset","0%").attr("stop-color","#FFFFFF").attr("stop-opacity","0.95")
    gradArctic.append("stop").attr("offset","40%").attr("stop-color","#B3E5FC").attr("stop-opacity","0.75")
    gradArctic.append("stop").attr("offset","100%").attr("stop-color","#4FC3F7").attr("stop-opacity","0.15")

    // Gradiente antártico: branco → azul gelo → transparente
    const gradAntarctic = defs.append("radialGradient")
        .attr("id","gradAntarctic").attr("cx","50%").attr("cy","80%")
        .attr("r","70%")
    gradAntarctic.append("stop").attr("offset","0%").attr("stop-color","#FFFFFF").attr("stop-opacity","0.9")
    gradAntarctic.append("stop").attr("offset","40%").attr("stop-color","#E1F5FE").attr("stop-opacity","0.7")
    gradAntarctic.append("stop").attr("offset","100%").attr("stop-color","#81D4FA").attr("stop-opacity","0.1")

    // Sphere (ocean background) — azul mais profundo
    svg.append("path")
        .datum({type: "Sphere"})
        .attr("fill","#061020")
        .attr("d", path)

    // Graticule grid — ligeiramente mais visível
    svg.append("path")
        .datum(d3.geoGraticule()())
        .attr("fill","none")
        .attr("stroke","rgba(255,255,255,.07)")
        .attr("stroke-width","0.5")
        .attr("d", path)

    // 7. Load world topojson
    let world
    try {
        world = await d3.json("/world-110m.json")
    } catch { return }

    // Countries — cor levemente mais clara para contrastar com o gelo
    svg.append("g")
        .selectAll("path")
        .data(topojson.feature(world, world.objects.countries).features)
        .join("path")
        .attr("fill","#1e3348")
        .attr("stroke","#0d1f30")
        .attr("stroke-width","0.4")
        .attr("d", path)

    // 8. Niño 3.4 region polygon (5N-5S, 120W-170W → lon -170 to -120)
    const nino34 = {
        type: "Feature",
        geometry: {
            type: "Polygon",
            coordinates: [[
                [-170, 5], [-120, 5], [-120, -5], [-170, -5], [-170, 5]
            ]]
        }
    }
    const nino34Path = svg.append("path")
        .datum(nino34)
        .attr("class", "map-nino34")
        .attr("d", path)

    // Label "Niño 3.4" sobre o polígono do Pacífico
    const [lx, ly] = projection([-145, 0]) || [0, 0]
    svg.append("text")
        .attr("x", lx).attr("y", ly + 4)
        .attr("text-anchor", "middle")
        .attr("font-size", Math.max(8, W * 0.009))
        .attr("font-weight", "600")
        .attr("fill", "rgba(255,255,255,0.6)")
        .attr("letter-spacing", "0.5")
        .style("pointer-events", "none")
        .text("Niño 3.4")

    // 9. IOD region (Índico: 50-110°E, 10S-10N)
    // IOD: contorno do Oceano Índico (sem fill — evita polígono escuro sobre terra/mar)
    const iodGeo = {
        type: "Feature",
        geometry: {
            type: "Polygon",
            coordinates: [[[50,-8],[90,-8],[90,8],[50,8],[50,-8]]]
        }
    }
    const iodPath = svg.append("path")
        .datum(iodGeo)
        .attr("fill", "none")
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "4 3")
        .attr("d", path)

    // 10. Ice cap circles — gradiente radial + borda brilhante
    const arcticPath = svg.append("path")
        .attr("fill","url(#gradArctic)")
        .attr("stroke","rgba(180,230,255,.6)")
        .attr("stroke-width","1")
    const antarcticPath = svg.append("path")
        .attr("fill","url(#gradAntarctic)")
        .attr("stroke","rgba(180,230,255,.5)")
        .attr("stroke-width","1")

    // 11. MJO badge externo inline com ONI
    const mjoPhase = mjoData?.phase ?? null
    const mjoAmp   = mjoData?.amplitude ?? 0
    const MJO_DESC = {
        1: "África/Índico O.", 2: "Índico O.", 3: "Índico L.",
        4: "Cont. Marítimo",  5: "Pacífico O.", 6: "Pacífico C.",
        7: "Pacífico L.",     8: "Hemis. Ocidental"
    }
    const mjoFooter = document.getElementById("mapMjoBadge")
    const mjoSep    = document.getElementById("mapMjoSep")
    if (mjoFooter && mjoPhase) {
        const active = mjoAmp >= 1.0
        mjoFooter.innerHTML = `<span class="map-mjo-dot ${active ? "active" : ""}"></span> MJO F${mjoPhase} · ${MJO_DESC[mjoPhase] || ""}${active ? ` · ${mjoAmp.toFixed(2)}` : ""}`
        if (mjoSep) mjoSep.style.display = ""
    }

    // 12. Animation
    let frameIdx = 0
    let timer = null

    function renderFrame(i) {
        const f = frames[i]
        const color = oniColor(f.oni)
        const icolor = iodColor(f.iod ?? 0)

        // Color Niño 3.4 region (Pacific)
        nino34Path.attr("fill", color)

        // IOD: contorno colorido (stroke only — sem fill para nao escurecer o mapa)
        iodPath.attr("stroke", icolor)

        // Ice caps
        const arcticR    = extentToRadius(f.arctic)
        const antarcticR = extentToRadius(f.antarctic)
        // Transição suave D3 para o gelo — mostra expansão/contração
        arcticPath.datum(d3.geoCircle().center([0, 90]).radius(arcticR)())
            .transition().duration(1000).ease(d3.easeCubicInOut)
            .attr("d", path)
        antarcticPath.datum(d3.geoCircle().center([0, -90]).radius(antarcticR)())
            .transition().duration(1000).ease(d3.easeCubicInOut)
            .attr("d", path)

        // UI labels
        const [y, m] = f.period.split("-")
        const monthNames = ["","Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        document.getElementById("mapMonthLabel").textContent = `${monthNames[+m]} ${y}`

        const oniSign = f.oni >= 0 ? "+" : ""
        const iodSign = f.iod >= 0 ? "+" : ""
        const stateMap = { EL_NINO: "El Niño", LA_NINA: "La Niña", NEUTRO: "Neutro" }

        // ONI badge
        document.getElementById("mapOniLabel").textContent =
            `${stateMap[f.classificacao] || f.classificacao} ONI ${oniSign}${f.oni.toFixed(2)}`

        // IOD badge — classifica por limiar ±0.4
        const iodClass = f.iod >= 0.4 ? "Positivo" : f.iod <= -0.4 ? "Negativo" : "Neutro"
        const iodEl = document.getElementById("mapIodLabel")
        if (iodEl) iodEl.textContent = `IOD ${iodSign}${f.iod.toFixed(2)} · ${iodClass}`

        // Timeline fill
        document.getElementById("mapTimelineFill").style.width =
            ((i + 1) / frames.length * 100).toFixed(1) + "%"
    }

    function nextFrame() {
        renderFrame(frameIdx)
        frameIdx = (frameIdx + 1) % frames.length
    }

    nextFrame()
    timer = setInterval(nextFrame, 1500)
    window._climateMapTimer = timer
}

