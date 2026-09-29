export function createHistoryPreview(file){
    return new Promise(resolve=>{
        const isPdf=
            file.type==="application/pdf"||
            file.name.toLowerCase().endsWith(".pdf");
        const isTextFile=file.type==="text/plain"||
            file.name.toLowerCase().endsWith(".txt");

        if(isTextFile){
            const previewLimit=16*1024;
            file.slice(0,previewLimit).text().then(text=>{
                const previewText=text+
                    (file.size>previewLimit?"\n\nPreview truncated.":"");
                resolve(
                    `data:text/plain;charset=utf-8,${encodeURIComponent(previewText)}`
                );
            }).catch(()=>resolve(null));
            return;
        }

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
                    1000/Math.max(img.naturalWidth,img.naturalHeight)
                );
                const canvas=document.createElement("canvas");
                canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));
                canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
                canvas.getContext("2d").drawImage(
                    img,
                    0,
                    0,
                    canvas.width,
                    canvas.height
                );
                resolve(canvas.toDataURL("image/jpeg",.78));
            };
            img.onerror=()=>resolve(null);
            img.src=reader.result;
        };

        reader.onerror=()=>resolve(null);
        reader.readAsDataURL(file);
    });
}

export function createTextDocumentPreview(file,previewDataUrl){
    const previewText=document.createElement("pre");
    const previewLimit=16*1024;

    previewText.className="text-document-preview";

    if(file&&typeof file.slice==="function"){
        previewText.textContent="Loading text preview…";
        file.slice(0,previewLimit).text().then(text=>{
            previewText.textContent=text+
                (file.size>previewLimit?"\n\nPreview truncated.":"");
        }).catch(()=>{
            previewText.textContent="Text preview unavailable.";
        });
    }else if(previewDataUrl&&previewDataUrl.startsWith("data:text/plain")){
        try{
            previewText.textContent=decodeURIComponent(
                previewDataUrl.slice(previewDataUrl.indexOf(",")+1)
            );
        }catch{
            previewText.textContent="Saved text preview unavailable.";
        }
    }else{
        previewText.textContent="Text preview unavailable for this saved document.";
    }

    return previewText;
}