const fileInput=document.getElementById("file-input"),
dropzone=document.getElementById("dropzone"),
dropzoneText=document.getElementById("dropzone-text"),
fileName=document.getElementById("file-name"),
preview=document.getElementById("preview"),
submitBtn=document.getElementById("submit-btn"),
errorEl=document.getElementById("error"),
historyCard=document.getElementById("history-card"),
historyList=document.getElementById("history-list"),
clearHistoryBtn=document.getElementById("clear-history-btn"),
resultsCard=document.getElementById("results-card"),
loadingEl=document.getElementById("loading"),
resultsEl=document.getElementById("results"),
reviewBadge=document.getElementById("review-badge"),
qualityWarning=document.getElementById("quality-warning"),
resetBtn=document.getElementById("reset-btn"),
downloadCsvBtn=document.getElementById("download-csv-btn"),
transactionsBlock=document.getElementById("transactions-block"),
transactionsBody=document.getElementById("transactions-body"),
selectedFileEl=document.getElementById("selected-file"),
selectedName=document.getElementById("selected-name"),
selectedSize=document.getElementById("selected-size"),
replaceBtn=document.getElementById("replace-btn"),
pipelineCard=document.getElementById("pipeline-card"),
pipelineStatus=document.getElementById("pipeline-status"),
resultPreview=document.getElementById("result-preview"),
resultFileName=document.getElementById("result-file-name");

let selectedFile=null,
currentResult=null,
selectedPreviewUrl=null,
currentDocumentName="",
selectedHistoryIds=[];

const HISTORY_KEY="ocr-extraction-history",
MAX_HISTORY_ITEMS=10;

const $=id=>document.getElementById(id);

const csvExtractedSection=$("csv-extracted-section"),
csvExtractedHead=$("csv-extracted-head"),
csvExtractedBody=$("csv-extracted-body");

function loadHistory(){
    try{
        const x=JSON.parse(localStorage.getItem(HISTORY_KEY)||"[]");
        return Array.isArray(x)?x:[];
    }catch{
        return[];
    }
}

function saveHistory(result,name,previewDataUrl){
    const h=loadHistory();

    h.unshift({
        id:`${Date.now()}-${Math.random().toString(16).slice(2)}`,
        name,
        createdAt:new Date().toISOString(),
        previewDataUrl,
        result
    });

    const savedHistory=h.slice(0,MAX_HISTORY_ITEMS);

    try{
        localStorage.setItem(
            HISTORY_KEY,
            JSON.stringify(savedHistory)
        );
    }catch{
        showError("Extraction succeeded, but browser history could not be saved.");
    }

    selectedHistoryIds=savedHistory.map(item=>item.id||"");
    renderHistory();
    renderCsvExtractedTable(result);
}

function formatHistoryDate(v){
    const d=new Date(v);
    return Number.isNaN(d.getTime())
        ?"Unknown date"
        :d.toLocaleString();
}

function createHistoryPreview(file){
    return new Promise(resolve=>{
        const isPdf=
            file.type==="application/pdf" ||
            file.name.toLowerCase().endsWith(".pdf");

        if(isPdf&&file.size>3*1024*1024){
            resolve(null);
            return;
        }

        const reader=new FileReader();

        reader.onload=()=>{
            if(isPdf){
                resolve(reader.result);
                return;
            }

            const img=new Image();

            img.onload=()=>{
                const scale=Math.min(
                    1,
                    1000/Math.max(
                        img.naturalWidth,
                        img.naturalHeight
                    )
                );

                const canvas=document.createElement("canvas");

                canvas.width=Math.max(
                    1,
                    Math.round(img.naturalWidth*scale)
                );

                canvas.height=Math.max(
                    1,
                    Math.round(img.naturalHeight*scale)
                );

                canvas
                    .getContext("2d")
                    .drawImage(
                        img,
                        0,
                        0,
                        canvas.width,
                        canvas.height
                    );

                resolve(
                    canvas.toDataURL("image/jpeg",.78)
                );
            };

            img.onerror=()=>resolve(null);
            img.src=reader.result;
        };

        reader.onerror=()=>resolve(null);
        reader.readAsDataURL(file);
    });
}

function openHistoryItem(item){

    if(!selectedHistoryIds.includes(item.id||"")){
        selectedHistoryIds=[item.id||""];
    }

    if(selectedPreviewUrl){
        URL.revokeObjectURL(selectedPreviewUrl);
        selectedPreviewUrl=null;
    }

    selectedFile={
        name:item.name||"Saved document",
        type:
            item.previewDataUrl &&
            item.previewDataUrl.startsWith("data:application/pdf")
                ?"application/pdf"
                :"image/jpeg"
    };

    currentDocumentName=item.name||"Saved document";
    selectedPreviewUrl=item.previewDataUrl||null;
    currentResult=item.result;

    renderResults(item.result);

    selectedFile=null;
    updateSubmitState();

    resultsCard.hidden=false;

    resultsCard.scrollIntoView({
        behavior:"smooth",
        block:"start"
    });

    renderHistory();
}

function getSelectedHistoryItems(){
    const hist=loadHistory();
    const ids=new Set(selectedHistoryIds);
    const seen=new Set();

    return hist.filter(item=>{
        const id=item.id||"";

        if(!ids.has(id)){
            return false;
        }

        const key=(item.name||"").trim().toLowerCase();

        if(seen.has(key)){
            return false;
        }

        seen.add(key);
        return true;
    });
}

function toggleHistorySelection(item){

    const id=item.id||"";
    const nameKey=(item.name||"").trim().toLowerCase();
    const exists=selectedHistoryIds.includes(id);

    if(exists){

        selectedHistoryIds=
            selectedHistoryIds.filter(v=>v!==id);

    }else{

        const selectedNames=
            new Set(
                getSelectedHistoryItems()
                    .map(x=>(x.name||"").trim().toLowerCase())
            );

        if(!selectedNames.has(nameKey)){
            selectedHistoryIds=[
                ...new Set([
                    ...selectedHistoryIds,
                    id
                ])
            ];
        }
    }

    renderHistory();
    renderCsvExtractedTable(currentResult||null);
}

function removeHistoryItem(item){

    const itemId=item.id||"";
    const history=loadHistory().filter(
        entry=>(entry.id||"")!==itemId
    );

    selectedHistoryIds=
        selectedHistoryIds.filter(id=>id!==itemId);

    if(
        currentDocumentName===
        (item.name||item.file_name||"")
    ){
        currentResult=null;
    }

    localStorage.setItem(
        HISTORY_KEY,
        JSON.stringify(history)
    );

    renderHistory();
    renderCsvExtractedTable(currentResult||null);
}

function renderHistory(){

    const h=loadHistory();

    historyList.innerHTML="";
    historyCard.hidden=h.length===0;

    h.forEach(item=>{

        const row=document.createElement("div");

        row.className=
            `history-item${
                selectedHistoryIds.includes(item.id||"")
                    ?" selected"
                    :""
            }`;

        const checkBtn=document.createElement("button");

        checkBtn.type="button";

        checkBtn.className=
            `history-check${
                selectedHistoryIds.includes(item.id||"")
                    ?" checked"
                    :""
            }`;

        checkBtn.setAttribute(
            "aria-label",
            `Select ${item.name||"document"}`
        );

        checkBtn.textContent=
            selectedHistoryIds.includes(item.id||"")
                ?"✓"
                :"";

        checkBtn.addEventListener(
            "click",
            ()=>{
                toggleHistorySelection(item);
            }
        );

        const details=document.createElement("div");

        const name=document.createElement("strong");
        name.textContent=item.name||"Untitled document";

        const date=document.createElement("span");
        date.textContent=formatHistoryDate(item.createdAt);

        details.append(name,date);

        const openBtn=document.createElement("button");

        openBtn.className="history-open-btn";
        openBtn.type="button";
        openBtn.textContent="Open";

        openBtn.addEventListener(
            "click",
            event=>{
                event.stopPropagation();
                openHistoryItem(item);
            }
        );

        const viewBtn=document.createElement("button");

        viewBtn.className="history-view-btn";
        viewBtn.type="button";
        viewBtn.textContent="View";

        viewBtn.addEventListener(
            "click",
            event=>{
                event.stopPropagation();
                viewHistoryItem(item);
            }
        );

        const removeBtn=document.createElement("button");

        removeBtn.className="history-remove-btn";
        removeBtn.type="button";
        removeBtn.textContent="×";
        removeBtn.setAttribute(
            "aria-label",
            `Remove ${item.name||"document"}`
        );

        removeBtn.addEventListener(
            "click",
            event=>{
                event.stopPropagation();
                removeHistoryItem(item);
            }
        );

        const actions=document.createElement("div");

        actions.className="history-actions";

        actions.append(
            openBtn,
            viewBtn,
            removeBtn
        );

        row.append(
            checkBtn,
            details,
            actions
        );

        historyList.appendChild(row);
    });
}


/* =========================================================
   DOCUMENT VIEW POPUP
   ========================================================= */

function viewHistoryItem(item) {
    const modal = document.getElementById("documentViewModal");
    const modalTitle = document.getElementById("documentViewTitle");
    const modalSubtitle = document.getElementById("documentViewSubtitle");
    const modalBody = document.getElementById("documentViewBody");

    if (!modal || !modalBody) {
        console.error("Document view modal not found.");
        return;
    }

    // Store the currently opened document
    currentDocumentName = item.name || item.file_name || "Document";
    currentResult = item.result;

    // Set popup title
    if (modalTitle) {
        modalTitle.textContent = currentDocumentName;
    }

    if (modalSubtitle) {
        modalSubtitle.textContent = "Extracted document information";
    }

    const previousSelectedFile = selectedFile;
    const previousPreviewUrl = selectedPreviewUrl;
    const previewIsPdf =
        item.previewDataUrl &&
        item.previewDataUrl.startsWith("data:application/pdf");

    selectedFile = {
        name: currentDocumentName,
        type: previewIsPdf ? "application/pdf" : "image/jpeg"
    };
    selectedPreviewUrl = item.previewDataUrl || null;

    // Render the selected document result
    renderResults(item.result);

    selectedFile = previousSelectedFile;
    selectedPreviewUrl = previousPreviewUrl;

    // Get the main results section
    const resultsElement = document.getElementById("results");

    if (!resultsElement) {
        console.error("Results section not found.");
        return;
    }

    // Clone the result content
    const clonedResults = resultsElement.cloneNode(true);

    // Remove duplicate IDs from cloned content
    clonedResults.querySelectorAll("[id]").forEach((element) => {
        element.removeAttribute("id");
    });

    // Remove the existing CSV section from the cloned result
    const existingCsvSection =
        clonedResults.querySelector(".csv-extracted-section");

    if (existingCsvSection) {
        existingCsvSection.remove();
    }

    // Create CSV section only for the selected document
    const singleDocumentCsvSection =
        createSingleDocumentCsvSection(item);

    // Add the CSV section to the popup
    clonedResults.appendChild(singleDocumentCsvSection);

    // Clear popup body
    modalBody.innerHTML = "";

    // Add selected document result
    modalBody.appendChild(clonedResults);

    // Show popup
    modal.classList.remove("hidden");

    // Prevent background scrolling
    document.body.style.overflow = "hidden";

    const closeButton =
        document.getElementById("documentViewClose");

    if (closeButton) {
        closeButton.onclick = () => {
            modal.classList.add("hidden");
            document.body.style.overflow = "";
        };
    }
}


/* =========================================================
   CREATE CSV SECTION FOR ONLY THE SELECTED DOCUMENT
   ========================================================= */

function createSingleDocumentCsvSection(item) {

    const section = document.createElement("div");

    section.className = "csv-extracted-section";

    const result = item.result || {};
    const fields = result.fields || {};

    const row = {
        source_file: item.name || item.file_name || "document",
        ...fields
    };

    const headers = Object.keys(row);

    /* -----------------------------
       Header
    ----------------------------- */

    const header = document.createElement("div");

    header.className = "csv-section-header";

    header.innerHTML = `
        <div>
            <div class="csv-section-title">
                <span class="csv-icon">CSV</span>
                <span>Extracted Information</span>
            </div>

            <p>
                Structured business data extracted from this document.
            </p>
        </div>
    `;

    section.appendChild(header);


    const tableScroll = document.createElement("div");

    tableScroll.className = "csv-table-scroll";

    const table = document.createElement("table");

    table.className = "csv-extracted-table";

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");

    headers.forEach((header) => {
        const th = document.createElement("th");
        th.textContent = header;
        headRow.appendChild(th);
    });

    thead.appendChild(headRow);

    const tbody = document.createElement("tbody");
    const bodyRow = document.createElement("tr");

    headers.forEach((header) => {
        const td = document.createElement("td");
        td.textContent = csvValue(row[header]);
        bodyRow.appendChild(td);
    });

    tbody.appendChild(bodyRow);
    table.append(thead, tbody);
    tableScroll.appendChild(table);
    section.appendChild(tableScroll);


    /* -----------------------------
       Download CSV Bar
       ----------------------------- */

    const downloadBar = document.createElement("div");

    downloadBar.className = "csv-download-bar";

    const downloadInfo = document.createElement("div");

    downloadInfo.innerHTML = `
        <span class="csv-download-icon">CSV</span>
        <span>
            CSV file will contain only this document's extracted data.
        </span>
    `;


    const downloadButton = document.createElement("button");

    downloadButton.type = "button";

    downloadButton.className = "secondary-btn";

    downloadButton.textContent = "↓ Download CSV";


    downloadButton.addEventListener("click", () => {

        const csvContent =
            singleDocumentFieldsToCsv(item);

        const blob = new Blob(
            [csvContent],
            {
                type: "text/csv;charset=utf-8;"
            }
        );

        const url = URL.createObjectURL(blob);

        const link = document.createElement("a");

        link.href = url;

        const originalName =
            item.name ||
            item.file_name ||
            "document";

        link.download =
            `${sanitizeFileName(originalName)}_extracted.csv`;

        document.body.appendChild(link);

        link.click();

        document.body.removeChild(link);

        URL.revokeObjectURL(url);
    });


    downloadBar.appendChild(downloadInfo);

    downloadBar.appendChild(downloadButton);

    section.appendChild(downloadBar);


    return section;
}


/* =========================================================
   CREATE CSV FOR ONLY ONE DOCUMENT
   ========================================================= */

function singleDocumentFieldsToCsv(item) {

    const result = item.result || {};

    const fields = result.fields || {};

    let rows = [];

    // CSV header
    rows.push(["Field", "Value"]);


    if (Array.isArray(fields)) {

        fields.forEach((field) => {

            if (typeof field === "object") {

                const name =
                    field.name ||
                    field.field ||
                    field.key ||
                    "Field";

                let value =
                    field.value ??
                    field.text ??
                    "";

                if (
                    typeof value === "object" &&
                    value !== null
                ) {
                    value = JSON.stringify(value);
                }

                rows.push([
                    name,
                    value
                ]);

            } else {

                rows.push([
                    "Field",
                    field
                ]);
            }
        });

    } else if (
        typeof fields === "object" &&
        fields !== null
    ) {

        Object.entries(fields).forEach(
            ([key, value]) => {

                if (
                    typeof value === "object" &&
                    value !== null
                ) {
                    value = JSON.stringify(value);
                }

                rows.push([
                    key,
                    value ?? ""
                ]);
            }
        );
    }


    // Convert to CSV
    return rows
        .map((row) =>
            row
                .map((value) => {

                    const text =
                        String(value ?? "");

                    // Escape quotes
                    const escaped =
                        text.replace(/"/g, '""');

                    // Wrap every value in quotes
                    return `"${escaped}"`;

                })
                .join(",")
        )
        .join("\n");
}


/* =========================================================
   SAFE FILE NAME
   ========================================================= */

function sanitizeFileName(name) {

    return String(name || "document")
        .replace(/\.[^/.]+$/, "")
        .replace(/[<>:"/\\|?*]+/g, "_")
        .replace(/\s+/g, "_")
        .substring(0, 100);
}

/* =========================================================
   FILE UPLOAD
   ========================================================= */

function updateSubmitState(){
    submitBtn.disabled=!selectedFile;
}

function showError(m){
    errorEl.textContent=m;
    errorEl.hidden=false;
}

function clearError(){
    errorEl.hidden=true;
    errorEl.textContent="";
}

function formatSize(bytes){
    return bytes<1024*1024
        ?`${(bytes/1024).toFixed(0)} KB`
        :`${(bytes/1024/1024).toFixed(1)} MB`;
}

function setFile(file){

    selectedFile=file;

    updateSubmitState();
    clearError();

    selectedName.textContent=file.name;

    selectedSize.textContent=
        `${file.type||"Document"} · ${formatSize(file.size)}`;

    selectedFileEl.hidden=false;

    const isPdf=
        file.type==="application/pdf" ||
        file.name.toLowerCase().endsWith(".pdf");

    if(selectedPreviewUrl){
        URL.revokeObjectURL(selectedPreviewUrl);
    }

    if(isPdf){

        preview.hidden=true;

        dropzoneText.hidden=false;

        dropzoneText.innerHTML=
            `<strong>Document selected</strong>
             <span>${file.name}</span>
             <small>PDF ready for processing</small>`;

    }else{

        selectedPreviewUrl=
            URL.createObjectURL(file);

        preview.src=selectedPreviewUrl;
        preview.hidden=false;
        dropzoneText.hidden=true;
    }
}

dropzone.onclick=()=>{
    fileInput.click();
};

fileInput.onchange=()=>{
    if(fileInput.files[0]){
        setFile(fileInput.files[0]);
    }
};

replaceBtn.onclick=()=>{
    fileInput.click();
};

["dragover","dragleave","drop"].forEach(
    evt=>{
        dropzone.addEventListener(
            evt,
            e=>{
                e.preventDefault();

                dropzone.classList.toggle(
                    "dragover",
                    evt==="dragover"
                );
            }
        );
    }
);

dropzone.ondrop=e=>{
    const f=e.dataTransfer.files[0];

    if(f){
        setFile(f);
    }
};


/* =========================================================
   PIPELINE
   ========================================================= */

function humanizeKey(key){
    return key
        .split("_")
        .map(
            w=>w.charAt(0).toUpperCase()+w.slice(1)
        )
        .join(" ");
}

function setPipeline(stage){

    const order=[
        "quality",
        "ocr",
        "classify",
        "extract",
        "validate"
    ];

    const idx=order.indexOf(stage);

    document
        .querySelectorAll(".pipe-step")
        .forEach((el,i)=>{
            el.classList.toggle(
                "active",
                i===idx
            );

            el.classList.toggle(
                "done",
                i<idx
            );
        });

    document
        .querySelectorAll(".pipe-line")
        .forEach((el,i)=>{
            el.classList.toggle(
                "done",
                i<idx
            );
        });

    pipelineStatus.textContent=
        stage==="validate"
            ?"VALIDATED"
            :"PROCESSING";
}

async function animatePipeline(){

    pipelineCard.hidden=false;

    const steps=[
        "quality",
        "ocr",
        "classify",
        "extract",
        "validate"
    ];

    for(const step of steps){

        setPipeline(step);

        await new Promise(
            r=>setTimeout(r,230)
        );
    }

    setPipeline("validate");
}


/* =========================================================
   PREVIEW
   ========================================================= */

function renderPreviewFromFile(savedName){

    resultPreview.innerHTML="";

    if(!selectedFile){

        resultFileName.textContent=
            savedName||"Saved document";

        const p=document.createElement("div");

        p.className="preview-placeholder";

        p.innerHTML=
            "<span>DOC</span><p>Saved document preview unavailable</p>";

        resultPreview.appendChild(p);

        return;
    }

    resultFileName.textContent=
        selectedFile.name;

    const isPdf=
        selectedFile.type==="application/pdf" ||
        selectedFile.name.toLowerCase().endsWith(".pdf");

    if(
        isPdf &&
        selectedPreviewUrl
    ){

        const frame=
            document.createElement("iframe");

        frame.src=selectedPreviewUrl;
        frame.title="Saved document preview";

        resultPreview.appendChild(frame);

    }else if(
        !isPdf &&
        selectedPreviewUrl
    ){

        const img=
            document.createElement("img");

        img.src=selectedPreviewUrl;
        img.alt="Uploaded document";

        resultPreview.appendChild(img);

    }else{

        const p=
            document.createElement("div");

        p.className="preview-placeholder";

        p.innerHTML=
            `<span>${isPdf?"PDF":"DOC"}</span>
             <p>Reprocess this document to restore its preview</p>`;

        resultPreview.appendChild(p);
    }
}


/* =========================================================
   RESULTS
   ========================================================= */

function renderResults(result){

    currentResult=result;

    const category=
        result.document_category||{};

    $("category-metric").textContent=
        category.category
            ?humanizeKey(category.category)
            :"Unknown";

    const detected=
        result._debug &&
        result._debug.detected_doc_type;

    $("detected-type-metric").textContent=
        detected
            ?`Detected capture type: ${humanizeKey(detected)}`
            :"Capture type not available";

    const confidence=
        result.ocr_confidence;

    const conf=
        typeof confidence==="number"
            ?confidence
            :0;

    $("confidence-metric").textContent=
        typeof confidence==="number"
            ?`${confidence.toFixed(1)}%`
            :"N/A";

    $("confidence-bar").style.width=
        `${Math.max(
            0,
            Math.min(100,conf)
        )}%`;

    const needsReview=
        !!(
            result.validation &&
            result.validation.needs_review
        );

    reviewBadge.textContent=
        needsReview
            ?"⚠ Needs review"
            :"✓ Validation passed";

    reviewBadge.className=
        `review-badge ${
            needsReview
                ?"warn"
                :"good"
        }`;

    $("validation-metric").textContent=
        needsReview
            ?"Review required"
            :"Passed";

    const warnings=
        (
            result.validation &&
            result.validation.quality_warnings
        )||[];

    $("quality-metric").textContent=
        warnings.length
            ?`${warnings.length} quality warning${
                warnings.length>1?"s":""
            }`
            :"No quality warnings";

    qualityWarning.textContent=
        warnings.length
            ?`Image quality warning: ${warnings.join("; ")}`
            :"";

    qualityWarning.hidden=
        !warnings.length;

    renderCsvExtractedTable(result);

    renderPreviewFromFile();

    const tx=result.transactions||[];

    transactionsBody.innerHTML="";

    tx.forEach(t=>{

        const row=
            document.createElement("tr");

        [
            t.date,
            t.description,
            t.debit,
            t.credit,
            t.balance
        ].forEach(c=>{

            const td=
                document.createElement("td");

            td.textContent=
                c==null
                    ?"—"
                    :c;

            row.appendChild(td);
        });

        transactionsBody.appendChild(row);
    });

    transactionsBlock.hidden=!tx.length;

    $("transaction-count").textContent=
        `${tx.length} record${
            tx.length===1
                ?""
                :"s"
        }`;

    const q=
        (
            result.validation &&
            result.validation.quality
        ) ||
        result.quality ||
        {};

    $("quality-resolution").textContent=
        q.resolution
            ?String(q.resolution)
            :"✓ Good";

    $("quality-brightness").textContent=
        q.brightness
            ?String(q.brightness)
            :"✓ Good";

    $("quality-blur").textContent=
        q.blur
            ?String(q.blur)
            :"✓ Good";

    $("quality-overall").textContent=
        warnings.length
            ?"⚠ Review"
            :"✓ Ready";

    $("quality-overall")
        .classList
        .toggle(
            "warn",
            warnings.length>0
        );

    resultsCard.hidden=false;
    loadingEl.hidden=true;
    resultsEl.hidden=false;

    pipelineCard.hidden=false;
    pipelineStatus.textContent="COMPLETE";

    document
        .querySelectorAll(".pipe-step")
        .forEach(x=>{
            x.classList.remove("active");
            x.classList.add("done");
        });
}


/* =========================================================
   CSV
   ========================================================= */

function downloadFile(
    content,
    filename,
    type
){

    const blob=
        new Blob(
            [content],
            {type}
        );

    const url=
        URL.createObjectURL(blob);

    const link=
        document.createElement("a");

    link.href=url;
    link.download=filename;
    link.click();

    setTimeout(
        ()=>{
            URL.revokeObjectURL(url);
        },
        100
    );
}

function csvCell(v){

    const t=
        v==null
            ?""
            :String(v);

    return `"${t.replace(
        /"/g,
        '""'
    )}"`;
}

function csvValue(value){

    if(value==null){
        return"";
    }

    if(Array.isArray(value)){
        return value.join("; ");
    }

    if(typeof value==="object"){
        return JSON.stringify(value);
    }

    return String(value);
}

function fieldType(value){

    if(
        value==null ||
        value===""
    ){
        return"string";
    }

    if(Array.isArray(value)){
        return"array";
    }

    if(typeof value==="number"){
        return"number";
    }

    if(typeof value==="boolean"){
        return"boolean";
    }

    if(typeof value==="object"){
        return"object";
    }

    return"string";
}

function csvRowData(result){

    return{
        source_file:
            currentDocumentName||"document",
        ...(result&&result.fields||{})
    };
}

function getCsvTableDataFromSelection(){

    const selectedItems=
        getSelectedHistoryItems();

    if(selectedItems.length){

        const rows=
            selectedItems.map(
                item=>({
                    source_file:
                        item.name||"document",
                    ...(item.result&&item.result.fields
                        ?item.result.fields
                        :{})
                })
            );

        const headers=
            Array.from(
                new Set(
                    rows.flatMap(
                        row=>Object.keys(row)
                    )
                )
            );

        return{
            headers,
            rows
        };
    }

    if(currentResult){

        const row=
            csvRowData(currentResult);

        return{
            headers:Object.keys(row),
            rows:[row]
        };
    }

    return{
        headers:[],
        rows:[]
    };
}

function renderCsvExtractedTable(result){

    const{
        headers,
        rows
    }=getCsvTableDataFromSelection();

    csvExtractedHead.innerHTML="";
    csvExtractedBody.innerHTML="";

    if(!headers.length){

        csvExtractedSection.hidden=true;

        return;
    }

    const headRow=
        document.createElement("tr");

    headers.forEach(header=>{

        const th=
            document.createElement("th");

        th.textContent=header;

        headRow.appendChild(th);
    });

    csvExtractedHead.appendChild(headRow);

    rows.forEach(row=>{

        const bodyRow=
            document.createElement("tr");

        headers.forEach(header=>{

            const td=
                document.createElement("td");

            td.textContent=
                csvValue(row[header]);

            bodyRow.appendChild(td);
        });

        csvExtractedBody.appendChild(
            bodyRow
        );
    });

    csvExtractedSection.hidden=false;
}

function fieldsToCsv(result){

    const{
        headers,
        rows
    }=getCsvTableDataFromSelection();

    if(!headers.length){
        return"\ufeff";
    }

    const csvLines=[
        headers.map(csvCell).join(",")
    ].concat(
        rows.map(
            row=>
                headers
                    .map(
                        header=>
                            csvCell(
                                csvValue(
                                    row[header]
                                )
                            )
                    )
                    .join(",")
        )
    );

    return"\ufeff"+
        csvLines.join("\r\n")+
        "\r\n";
}

function resultToCsv(result){

    const rows=[];

    const addRow=(...values)=>
        rows.push(
            values
                .map(csvCell)
                .join(",")
        );

    const category=
        result.document_category||{};

    const validation=
        result.validation||{};

    const quality=
        validation.quality||
        result.quality||
        {};

    addRow("DOCUMENT EXTRACTION");
    addRow("Field","Value");

    addRow(
        "Document type",
        category.category
            ?humanizeKey(category.category)
            :""
    );

    addRow(
        "Capture type",
        result._debug &&
        result._debug.detected_doc_type
            ?humanizeKey(
                result._debug.detected_doc_type
            )
            :""
    );

    addRow(
        "OCR confidence",
        result.ocr_confidence==null
            ?""
            :`${result.ocr_confidence}%`
    );

    addRow(
        "Validation",
        validation.needs_review
            ?"Review required"
            :"Passed"
    );

    addRow(
        "Quality warnings",
        (
            validation.quality_warnings||[]
        ).join("; ")
    );

    addRow(
        "Resolution",
        quality.resolution||""
    );

    addRow(
        "Brightness",
        quality.brightness||""
    );

    addRow(
        "Blur / noise",
        quality.blur||""
    );

    rows.push("");

    addRow(
        "EXTRACTED FIELDS"
    );

    addRow(
        "Field",
        "Value"
    );

    Object.entries(
        result.fields||{}
    )
    .filter(
        ([,value])=>
            value!==null &&
            value!==""
    )
    .forEach(
        ([field,value])=>{
            addRow(
                humanizeKey(field),
                csvValue(value)
            );
        }
    );

    const transactions=
        result.transactions||[];

    if(transactions.length){

        rows.push("");

        addRow("TRANSACTIONS");

        addRow(
            "Date",
            "Description",
            "Debit",
            "Credit",
            "Balance"
        );

        transactions.forEach(
            transaction=>{
                addRow(
                    transaction.date,
                    transaction.description,
                    transaction.debit,
                    transaction.credit,
                    transaction.balance
                );
            }
        );
    }

    return"\ufeff"+
        rows.join("\r\n")+
        "\r\n";
}


/* =========================================================
   RESET
   ========================================================= */

function resetForm(){

    selectedFile=null;
    currentResult=null;
    selectedHistoryIds=[];

    fileInput.value="";
    preview.src="";
    preview.hidden=true;

    dropzoneText.hidden=false;

    dropzoneText.innerHTML=
        '<strong>Drag & drop your document here</strong><span>or <u>browse files</u> from your computer</span><small>Maximum file size: 15 MB</small>';

    selectedFileEl.hidden=true;

    resultsCard.hidden=true;
    pipelineCard.hidden=true;
    resultsEl.hidden=true;
    loadingEl.hidden=true;

    csvExtractedSection.hidden=true;
    csvExtractedHead.innerHTML="";
    csvExtractedBody.innerHTML="";

    clearError();
    updateSubmitState();
    renderHistory();
}


/* =========================================================
   PROCESS DOCUMENT
   ========================================================= */

submitBtn.onclick=async()=>{

    if(!selectedFile){
        return;
    }

    currentDocumentName=
        selectedFile.name;

    clearError();

    resultsCard.hidden=false;
    resultsEl.hidden=true;
    loadingEl.hidden=false;

    pipelineCard.hidden=false;
    pipelineStatus.textContent="PROCESSING";

    submitBtn.disabled=true;

    animatePipeline();

    const fd=new FormData();

    fd.append(
        "file",
        selectedFile
    );

    try{

        const response=
            await fetch(
                "/api/process",
                {
                    method:"POST",
                    body:fd
                }
            );

        const data=
            await response.json();

        if(!response.ok){
            throw new Error(
                data.error||
                "Something went wrong processing the document."
            );
        }

        const historyPreview=
            await createHistoryPreview(
                selectedFile
            );

        renderResults(data);

        saveHistory(
            data,
            selectedFile.name,
            historyPreview
        );

        resultsCard.scrollIntoView({
            behavior:"smooth",
            block:"start"
        });

    }catch(err){

        resultsCard.hidden=true;
        pipelineCard.hidden=true;

        showError(err.message);

    }finally{

        updateSubmitState();
    }
};


/* =========================================================
   BUTTONS
   ========================================================= */

resetBtn.onclick=resetForm;

downloadCsvBtn.onclick=()=>{

    if(currentResult){

        downloadFile(
            fieldsToCsv(currentResult),
            "extracted-information.csv",
            "text/csv;charset=utf-8"
        );
    }
};

clearHistoryBtn.onclick=()=>{

    localStorage.removeItem(
        HISTORY_KEY
    );

    renderHistory();
};


/* =========================================================
   INITIAL LOAD
   ========================================================= */

renderHistory();