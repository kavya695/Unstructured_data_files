const PIPELINE_CONFIGS={
    image:{
        subtitle:"From raw document to validated structured data.",
        steps:[
            ["quality","Quality","Image analysis"],
            ["ocr","OCR","Text recognition"],
            ["classify","Classify","Document type"],
            ["extract","Extract","Business fields"],
            ["validate","Validate","Trust checks"]
        ]
    },
    text:{
        subtitle:"From raw text to classified structured data.",
        steps:[
            ["extract-clean","Extract & Clean","Read and normalize text"],
            ["chunk","Chunk","Split text into sections"],
            ["discover-fields","Discover Fields","Find label-value fields"],
            ["tfidf","TF-IDF","Convert text into vectors"],
            ["cluster","Cluster","Group similar sections"],
            ["infer-schema","Infer Schema","Build field structure"],
            ["classify-text","Classify","Document type scoring"]
        ]
    }
};

export function renderPipeline({pipeline,status,subtitle,processingType,state}){
    const config=PIPELINE_CONFIGS[processingType]||PIPELINE_CONFIGS.image;

    if(!pipeline){
        return;
    }

    const nodes=[];

    config.steps.forEach((step,index)=>{
        const [key,title,description]=step;
        const node=document.createElement("div");
        const icon=document.createElement("span");
        const heading=document.createElement("strong");
        const detail=document.createElement("small");

        node.className="pipe-step";
        node.dataset.step=key;

        if(state==="complete"){
            node.classList.add("done");
        }

        icon.className="pipe-icon";
        icon.textContent=String(index+1).padStart(2,"0");
        heading.textContent=title;
        detail.textContent=description;
        node.append(icon,heading,detail);
        nodes.push(node);

        if(index<config.steps.length-1){
            const line=document.createElement("div");
            line.className="pipe-line";

            if(state==="complete"){
                line.classList.add("done");
            }

            nodes.push(line);
        }
    });

    pipeline.replaceChildren(...nodes);

    if(subtitle){
        subtitle.textContent=config.subtitle;
    }

    if(status){
        status.textContent={
            ready:"READY",
            processing:"PROCESSING",
            complete:"COMPLETE",
            failed:"FAILED"
        }[state]||"READY";
    }
}