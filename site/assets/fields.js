export const fields = [
    {id:'agents',en:'Agent systems',zh:'Agent 系统',icon:'⌘',tags:['agents','agent','agentic','coding_agent','computer_use','tool_use','tool_calling','tool-use','memory','ai_research','scientific_agent','agent evaluation','legal agent','智能体'],subs:[['Coding agents','编程 Agent',['coding_agent','code agent']],['Computer use','计算机操作',['computer_use']],['Search & research','搜索与研究',['search','deep research','ai_research','scientific_agent']],['Tool use','工具使用',['tool_use','tool_calling','tool-use']],['Memory','记忆',['memory']],['Data analysis','数据分析',['data_analysis','AI数据分析']]]},
    {id:'coding',en:'Coding',zh:'代码与工程',icon:'⌗',tags:['code','coding','coding_agent','frontend_development','代码','代码工程','code agent','github issue resolution','competitive programming','代码生成'],subs:[['Software engineering','软件工程',['code','coding','code agent','代码工程','github issue resolution']],['Coding agents','编程 Agent',['coding_agent','code agent']],['Frontend development','前端开发',['frontend_development']],['Competitive programming','竞赛编程',['competitive programming']]]},
    {id:'reasoning',en:'Reasoning & knowledge',zh:'推理与知识',icon:'◇',tags:['reasoning','math','knowledge','general','long_context','long context','long-context','language','comprehension','instruction_following','instruction following','structured_output','逻辑推理','知识储备','strong reasoning','深度推理'],subs:[['Reasoning','推理',['reasoning','strong reasoning','逻辑推理']],['Mathematics','数学',['math','数学','数理能力']],['Knowledge','知识',['knowledge','知识储备']],['Long context','长上下文',['long_context','long context','long-context']],['Instructions & output','指令与输出',['instruction_following','instruction following','structured_output']]]},
    {id:'multimodal',en:'Multimodal',zh:'多模态',icon:'◫',tags:['multimodal','vision','vlm','video','video understanding','audio','audio understanding','image understanding','spatial_reasoning','spatial understanding','embodied ai','robotics','image-generation','text-to-image'],subs:[['Vision & images','视觉与图像',['vision','image understanding','image_to_text']],['Video understanding','视频理解',['video','video understanding','video-understanding']],['Audio & speech','音频与语音',['audio','audio understanding','speech_to_text']],['Spatial & embodied','空间与具身',['spatial_reasoning','spatial understanding','embodied ai','robotics']],['Image generation','图像生成',['image-generation','text-to-image','visual generation']]]},
    {id:'science',en:'AI for science',zh:'科学智能',icon:'✳',tags:['science','ai for science','scientific reasoning','physics','biology','chemistry','scientific_agent','ai_research','engineering','科学智能'],subs:[['Scientific reasoning','科学推理',['science','scientific reasoning']],['Physics','物理',['physics']],['Biology & chemistry','生物与化学',['biology','chemistry']],['Research agents','科研 Agent',['scientific_agent','ai_research']]]},
    {id:'applied',en:'Applied AI',zh:'行业应用',icon:'▥',tags:['healthcare','medical','health','finance','economics','legal','legal ai','business','professional','productivity','psychology','education','医学','医疗','金融','教育','法律'],subs:[['Health & medicine','医疗与健康',['healthcare','medical','health','医学','医疗']],['Finance & economics','金融与经济',['finance','economics','金融']],['Legal','法律',['legal','legal ai','legal agent']],['Work & productivity','工作与生产力',['business','professional','productivity','data_analysis']]]},
    {id:'safety',en:'Safety & alignment',zh:'安全与对齐',icon:'◈',tags:['safety','safety alignment','security','privacy','jailbreak','factuality','factual reliability','faithfulness','hallucination','安全','安全对齐'],subs:[['Safety & security','安全',['safety','safety alignment','security']],['Factual reliability','事实可靠性',['factuality','factual reliability','faithfulness','hallucination']],['Privacy','隐私',['privacy']]]},
    {id:'other',en:'Other research',zh:'其他研究',icon:'⋯',tags:[],subs:[]}
  ];
export function recordFields(record) {
 const tags = [...(record.tags || record.categories || [])].map(t => String(t).toLowerCase());
 const found=fields.filter(f=>f.id!=="other" && f.tags.some(t=>tags.includes(t.toLowerCase()))).map(f=>f.id);
 return found.length?found:["other"];
}
export function matchesField(record, field="all", sub="") {
 if(field==="all") return true;
 if(!recordFields(record).includes(field)) return false;
 const direction=fields.find(f=>f.id===field)?.subs.find(s=>s[0]===sub);
 if(!direction)return true;
 const tags=[...(record.tags || record.categories || [])].map(t=>String(t).toLowerCase());
 return direction[2].some(t=>tags.includes(t.toLowerCase()));
}
