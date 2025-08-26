import os
import time
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import gradio as gr

# Import config and utilities
import config
from utils.helpers import (
    ensure_dir, read_text, write_text, make_project_folder, 
    stage_filenames, secfmt, now_hhmmss
)
from utils.state_manager import StateManager
from utils.resource_monitor import ResourceMonitor
from utils.progress_tracker import StageProgress

# Import modules
from modules.asr import run_asr
from modules.text_cleaner import clean_text_gui, clean_text_basic, EngineConfig
from modules.translator import translate_text
from modules.tts import synthesize_tts

class S2TSPipeline:
    """Main pipeline class that orchestrates the S2TS process."""
    
    def __init__(self):
        self.state_manager = StateManager()
        self.resource_monitor = ResourceMonitor()
        self.progress_tracker = StageProgress()
        self.is_running = False
        self.current_project = None
        
        # Ensure directories exist
        ensure_dir(config.INCOMING_DIR)
        ensure_dir(config.PROJECTS_DIR)
        ensure_dir(config.PROMPTS_DIR)
        
        # Create default prompt files if missing
        if not Path(config.CORRECTOR_PROMPT_FILE).exists():
            write_text(Path(config.CORRECTOR_PROMPT_FILE), config.DEFAULT_CORRECTOR_PROMPT)
        if not Path(config.TRANSLATOR_PROMPT_FILE).exists():
            write_text(Path(config.TRANSLATOR_PROMPT_FILE), config.DEFAULT_TRANSLATOR_PROMPT)
    
    def run_full_pipeline(self, audio_path: str, enable_asr: bool, enable_clean: bool, 
                         enable_translate: bool, enable_tts: bool, target_langs: list,
                         engine_name: str, ref_audio_numpy: Optional[tuple], 
                         ref_text: str, manual_text: str = "", progress_cb: Callable = None):
        """Run the full pipeline with selected modules enabled."""
        self.is_running = True
        results = {}
        
        # Prepare project
        audio_file = Path(audio_path) if audio_path else None
        if audio_file:
            proj_dir = make_project_folder(audio_file)
            base = audio_file.stem
            self.current_project = proj_dir
        else:
            # Use manual text input
            base = f"manual_{int(time.time())}"
            proj_dir = Path(config.PROJECTS_DIR) / f"Proj-{base}"
            ensure_dir(proj_dir)
            self.current_project = proj_dir
        
        # ASR Stage
        asr_output = manual_text
        asr_time = 0
        if enable_asr and audio_file:
            if progress_cb:
                progress_cb(0, 0, f"[{now_hhmmss()}] Starting ASR...")
            
            files = stage_filenames(proj_dir, base)
            asr_text, asr_time, asr_stdout = run_asr(
                audio_file, files["asr"], 
                lambda p, m: progress_cb(0, p, f"[ASR] {m}") if progress_cb else None
            )
            write_text(files["asr"], asr_text)
            asr_output = asr_text
            results['asr'] = {
                'output': asr_text,
                'time_taken': asr_time,
                'file_path': str(files["asr"])
            }
            
            if progress_cb:
                progress_cb(0, 100, f"[ASR] Completed in {secfmt(asr_time)}")
        
        # Text Cleaning Stage
        cleaned_text = asr_output
        clean_time = 0
        if enable_clean and asr_output.strip():
            if progress_cb:
                progress_cb(1, 0, f"[{now_hhmmss()}] Starting text cleaning...")
            
            # Load engine config
            engines = self._load_engines()
            cfg_raw = engines.get(engine_name, list(engines.values())[0])
            cfg = EngineConfig(
                url=cfg_raw["url"],
                login_required=cfg_raw.get("login_required", True),
                copy_btn_coords=tuple(cfg_raw.get("copy_btn_coords", (0, 0)))
            )
            
            files = stage_filenames(proj_dir, base)
            cleaned, clean_time = clean_text_gui(
                asr_output, cfg,
                lambda p, m: progress_cb(1, p, f"[Clean] {m}") if progress_cb else None
            )
            write_text(files["clean"], cleaned)
            cleaned_text = cleaned
            results['clean'] = {
                'output': cleaned,
                'time_taken': clean_time,
                'file_path': str(files["clean"])
            }
            
            if progress_cb:
                progress_cb(1, 100, f"[Clean] Completed in {secfmt(clean_time)}")
        
        # Translation Stage
        translations = {}
        trans_times = {}
        if enable_translate and cleaned_text.strip():
            if progress_cb:
                progress_cb(2, 0, f"[{now_hhmmss()}] Starting translation...")
            
            # Load engine config
            engines = self._load_engines()
            cfg_raw = engines.get(engine_name, list(engines.values())[0])
            cfg = EngineConfig(
                url=cfg_raw["url"],
                login_required=cfg_raw.get("login_required", True),
                copy_btn_coords=tuple(cfg_raw.get("copy_btn_coords", (0, 0)))
            )
            
            for i, lang in enumerate(target_langs):
                if progress_cb:
                    progress_cb(2, i * 100 // len(target_langs), 
                               f"[Translate] Starting {lang} translation...")
                
                files = stage_filenames(proj_dir, base, lang)
                translated, trans_time = translate_text(
                    cleaned_text, lang, cfg,
                    lambda p, m: progress_cb(2, i * 100 // len(target_langs) + p // len(target_langs), 
                                           f"[Translate-{lang}] {m}") if progress_cb else None
                )
                write_text(files["trans"], translated)
                translations[lang] = translated
                trans_times[lang] = trans_time
                
                if progress_cb:
                    progress_cb(2, (i + 1) * 100 // len(target_langs), 
                               f"[Translate-{lang}] Completed in {secfmt(trans_time)}")
            
            results['translate'] = {
                'outputs': translations,
                'times': trans_times
            }
        
        # TTS Stage
        tts_outputs = {}
        tts_times = {}
        if enable_tts:
            if progress_cb:
                progress_cb(3, 0, f"[{now_hhmmss()}] Starting TTS...")
            
            # Use translations if available, otherwise use cleaned text
            texts_to_speak = translations if translations else {'original': cleaned_text}
            
            for i, (lang, text) in enumerate(texts_to_speak.items()):
                if progress_cb:
                    progress_cb(3, i * 100 // len(texts_to_speak), 
                               f"[TTS] Generating {lang} audio...")
                
                files = stage_filenames(proj_dir, base, lang)
                tts_time = synthesize_tts(
                    text, ref_audio_numpy, ref_text, files["tts"],
                    lambda p, m: progress_cb(3, i * 100 // len(texts_to_speak) + p // len(texts_to_speak), 
                                           f"[TTS-{lang}] {m}") if progress_cb else None
                )
                tts_outputs[lang] = str(files["tts"])
                tts_times[lang] = tts_time
                
                if progress_cb:
                    progress_cb(3, (i + 1) * 100 // len(texts_to_speak), 
                               f"[TTS-{lang}] Completed in {secfmt(tts_time)}")
            
            results['tts'] = {
                'outputs': tts_outputs,
                'times': tts_times
            }
        
        self.is_running = False
        return results
    
    def _load_engines(self) -> Dict[str, Any]:
        """Load engine configurations from JSON file."""
        engines_file = Path("engines.json")
        if engines_file.exists():
            try:
                with open(engines_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("engines", {})
            except Exception as e:
                print(f"Error loading engines.json: {e}")
        return {}
    
    def get_resource_stats(self) -> Dict[str, float]:
        """Get current resource usage statistics."""
        return self.resource_monitor.get_stats()
    
    def start_resource_monitoring(self) -> None:
        """Start background resource monitoring."""
        self.resource_monitor.start_monitoring(interval=5)
    
    def stop_resource_monitoring(self) -> None:
        """Stop background resource monitoring."""
        self.resource_monitor.stop_monitoring()

# Create global pipeline instance
pipeline = S2TSPipeline()

# Start resource monitoring
pipeline.start_resource_monitoring()

# Create Gradio UI
def create_ui():
    with gr.Blocks(
        theme=gr.themes.Soft(
            primary_hue=config.THEME_PRIMARY,
            secondary_hue=config.THEME_SECONDARY,
            neutral_hue=config.THEME_NEUTRAL,
            font=["Inter", "sans-serif"]
        ).set(
            body_background_fill=config.DARK_BG_GRADIENT,
            block_background_fill="#111827",
            block_title_text_color="white",
            block_border_color="#334155",
            body_text_color="#d1d5db",
            button_primary_background_fill="#0ea5e9",
            button_primary_text_color="white",
            button_secondary_background_fill="#1e293b",
            button_secondary_text_color="#e5e7eb"
        ),
        css="""
        .shadow-card { 
            box-shadow: 0 10px 25px rgba(0,0,0,0.35); 
            border-radius: 16px; 
            padding: 16px;
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid #334155;
        }
        .logbox { 
            white-space: pre-wrap; 
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; 
            font-size: 13px; 
            background: #0f172a;
            color: #e2e8f0;
        }
        .progress-bar {
            border-radius: 8px;
            height: 20px;
        }
        .resource-meter {
            height: 12px;
            border-radius: 6px;
        }
        .neon-text {
            text-shadow: 0 0 5px #0ea5e9, 0 0 10px #0ea5e9, 0 0 15px #0ea5e9;
            color: white;
        }
        """
    ) as demo:
        # Header
        gr.Markdown(
            f"""
            <div style="text-align:center;padding:18px;border-radius:16px;background:#0f172a;box-shadow:0 4px 12px rgba(0,0,0,0.6);">
                <h1 class="neon-text" style="margin:0;font-size:2.5em;">{config.APP_TITLE}</h1>
                <p style="color:#94a3b8;margin-top:6px;font-size:1.1em;">ASR (Tamil) → Clean Tamil → Translate (Hindi/Kannada/Telugu) → TTS (Indic-F5)</p>
            </div>
            """
        )
        
        with gr.Row():
            with gr.Column(scale=1):
                # Module toggles
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 🎛️ Module Selection")
                    with gr.Row():
                        enable_asr = gr.Checkbox(value=True, label="ASR", interactive=True)
                        enable_clean = gr.Checkbox(value=True, label="Text Cleaning", interactive=True)
                        enable_translate = gr.Checkbox(value=True, label="Translation", interactive=True)
                        enable_tts = gr.Checkbox(value=True, label="TTS", interactive=True)
                
                # Input section
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 📥 Input")
                    audio_in = gr.Audio(label="Upload Input Audio (Tamil)", type="filepath")
                    
                    # Manual text input (shown when ASR is disabled)
                    manual_text = gr.Textbox(
                        label="Manual Text Input", 
                        lines=4, 
                        visible=False,
                        placeholder="Enter text manually if ASR is disabled"
                    )
                
                # Language selection
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 🌐 Translation Languages")
                    target_langs = gr.CheckboxGroup(
                        choices=list(config.LANG_LABELS.keys()),
                        value=["Hindi"],
                        label="Target Languages"
                    )
                
                # Engine selection
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 🔧 Engine Settings")
                    engine = gr.Dropdown(
                        list(pipeline._load_engines().keys()), 
                        value=list(pipeline._load_engines().keys())[0] if pipeline._load_engines() else None,
                        label="AI Engine"
                    )
                    reload_btn = gr.Button("🔄 Reload Engines", variant="secondary", size="sm")
                
                # TTS reference
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 🎵 TTS Reference")
                    ref_audio = gr.Audio(type="numpy", label="Reference Audio")
                    ref_text = gr.Textbox(
                        lines=2, 
                        label="Reference Text",
                        placeholder="Enter the text that matches the reference audio"
                    )
                
                # Action buttons
                with gr.Row():
                    run_btn = gr.Button("🚀 Run Full Pipeline", variant="primary", size="lg")
                    stop_btn = gr.Button("⏹️ Stop", variant="stop", size="lg")
            
            with gr.Column(scale=2):
                # Progress section
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 📊 Progress")
                    
                    # Progress bars for each stage
                    asr_progress = gr.Slider(
                        minimum=0, maximum=100, value=0, 
                        label="ASR Progress", interactive=False,
                        elem_classes="progress-bar"
                    )
                    clean_progress = gr.Slider(
                        minimum=0, maximum=100, value=0, 
                        label="Text Cleaning Progress", interactive=False,
                        elem_classes="progress-bar"
                    )
                    translate_progress = gr.Slider(
                        minimum=0, maximum=100, value=0, 
                        label="Translation Progress", interactive=False,
                        elem_classes="progress-bar"
                    )
                    tts_progress = gr.Slider(
                        minimum=0, maximum=100, value=0, 
                        label="TTS Progress", interactive=False,
                        elem_classes="progress-bar"
                    )
                    
                    # Progress log
                    log = gr.Textbox(
                        label="Progress Log", 
                        value="", 
                        interactive=False, 
                        lines=10, 
                        elem_classes="logbox"
                    )
                
                # Resource monitoring
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 📈 System Resources")
                    
                    with gr.Row():
                        cpu_usage = gr.Slider(
                            minimum=0, maximum=100, value=0,
                            label="CPU Usage %", interactive=False,
                            elem_classes="resource-meter"
                        )
                        ram_usage = gr.Slider(
                            minimum=0, maximum=100, value=0,
                            label="RAM Usage %", interactive=False,
                            elem_classes="resource-meter"
                        )
                    
                    with gr.Row():
                        gpu_usage = gr.Slider(
                            minimum=0, maximum=100, value=0,
                            label="GPU Usage %", interactive=False,
                            elem_classes="resource-meter"
                        )
                        gpu_mem_usage = gr.Slider(
                            minimum=0, maximum=100, value=0,
                            label="GPU Memory %", interactive=False,
                            elem_classes="resource-meter"
                        )
                    
                    disk_usage = gr.Slider(
                        minimum=0, maximum=100, value=0,
                        label="Disk Usage %", interactive=False,
                        elem_classes="resource-meter"
                    )
                
                # Results section
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### 📂 Output Results")
                    
                    with gr.Tabs():
                        with gr.TabItem("ASR"):
                            asr_output = gr.Textbox(label="ASR Result", interactive=False, lines=5)
                        with gr.TabItem("Cleaned Text"):
                            clean_output = gr.Textbox(label="Cleaned Text", interactive=False, lines=5)
                        with gr.TabItem("Hindi"):
                            with gr.Row():
                                hi_trans = gr.Textbox(label="Hindi Translation", interactive=False, lines=4)
                                hi_audio = gr.Audio(label="Hindi TTS", interactive=False)
                        with gr.TabItem("Kannada"):
                            with gr.Row():
                                kn_trans = gr.Textbox(label="Kannada Translation", interactive=False, lines=4)
                                kn_audio = gr.Audio(label="Kannada TTS", interactive=False)
                        with gr.TabItem("Telugu"):
                            with gr.Row():
                                te_trans = gr.Textbox(label="Telugu Translation", interactive=False, lines=4)
                                te_audio = gr.Audio(label="Telugu TTS", interactive=False)
                
                # Summary
                with gr.Group(elem_classes="shadow-card"):
                    gr.Markdown("### ⏱️ Timing Summary")
                    summary = gr.JSON(label="Processing Times", value={})
        
        # Dynamic UI updates
        def toggle_ui(asr_enabled, clean_enabled, translate_enabled, tts_enabled):
            return [
                gr.Textbox(visible=not asr_enabled),  # Manual text input
                gr.Audio(visible=asr_enabled),        # Audio input
                gr.Group(visible=tts_enabled),        # TTS reference section
            ]
        
        # Update UI when toggles change
        enable_asr.change(
            toggle_ui, 
            [enable_asr, enable_clean, enable_translate, enable_tts],
            [manual_text, audio_in, ref_audio]
        )
        enable_tts.change(
            toggle_ui, 
            [enable_asr, enable_clean, enable_translate, enable_tts],
            [manual_text, audio_in, ref_audio]
        )
        
        # Reload engines button
        def reload_engines_fn():
            engines = pipeline._load_engines()
            choices = list(engines.keys())
            return gr.Dropdown(choices=choices, value=choices[0] if choices else None)
        
        reload_btn.click(
            fn=reload_engines_fn,
            inputs=[],
            outputs=[engine]
        )
        
        # Pipeline execution
        def run_pipeline_wrapper(audio_path, asr_enabled, clean_enabled, translate_enabled, tts_enabled,
                               target_langs, engine_name, ref_audio_np, ref_text_str, manual_text_str):
            # Prepare progress callback
            def progress_callback(stage_idx, progress, message):
                # Update the appropriate progress bar
                if stage_idx == 0:
                    yield {asr_progress: progress, log: message}
                elif stage_idx == 1:
                    yield {clean_progress: progress, log: message}
                elif stage_idx == 2:
                    yield {translate_progress: progress, log: message}
                elif stage_idx == 3:
                    yield {tts_progress: progress, log: message}
                else:
                    yield {log: message}
            
            # Run the pipeline
            results = pipeline.run_full_pipeline(
                audio_path, asr_enabled, clean_enabled, translate_enabled, tts_enabled,
                target_langs, engine_name, ref_audio_np, ref_text_str, manual_text_str,
                progress_callback
            )
            
            # Prepare outputs
            output_dict = {
                asr_output: results.get('asr', {}).get('output', ''),
                clean_output: results.get('clean', {}).get('output', ''),
                summary: {
                    'ASR': secfmt(results.get('asr', {}).get('time_taken', 0)),
                    'Text Cleaning': secfmt(results.get('clean', {}).get('time_taken', 0)),
                    'Translation': {lang: secfmt(time) for lang, time in results.get('translate', {}).get('times', {}).items()},
                    'TTS': {lang: secfmt(time) for lang, time in results.get('tts', {}).get('times', {}).items()}
                }
            }
            
            # Add language-specific outputs
            if 'Hindi' in results.get('translate', {}).get('outputs', {}):
                output_dict[hi_trans] = results['translate']['outputs']['Hindi']
                if 'Hindi' in results.get('tts', {}).get('outputs', {}):
                    output_dict[hi_audio] = results['tts']['outputs']['Hindi']
            
            if 'Kannada' in results.get('translate', {}).get('outputs', {}):
                output_dict[kn_trans] = results['translate']['outputs']['Kannada']
                if 'Kannada' in results.get('tts', {}).get('outputs', {}):
                    output_dict[kn_audio] = results['tts']['outputs']['Kannada']
            
            if 'Telugu' in results.get('translate', {}).get('outputs', {}):
                output_dict[te_trans] = results['translate']['outputs']['Telugu']
                if 'Telugu' in results.get('tts', {}).get('outputs', {}):
                    output_dict[te_audio] = results['tts']['outputs']['Telugu']
            
            yield output_dict
        
        run_btn.click(
            fn=run_pipeline_wrapper,
            inputs=[audio_in, enable_asr, enable_clean, enable_translate, enable_tts,
                   target_langs, engine, ref_audio, ref_text, manual_text],
            outputs=[asr_output, clean_output, hi_trans, hi_audio, kn_trans, kn_audio, 
                    te_trans, te_audio, summary, asr_progress, clean_progress, 
                    translate_progress, tts_progress, log],
            queue=True
        )
        
        # Resource monitoring update
        def update_resource_stats():
            stats = pipeline.get_resource_stats()
            return {
                cpu_usage: stats['cpu'],
                ram_usage: stats['memory'],
                gpu_usage: stats['gpu'],
                gpu_mem_usage: stats['gpu_memory'],
                disk_usage: stats['disk']
            }
        
        demo.load(
            update_resource_stats,
            inputs=None,
            outputs=[cpu_usage, ram_usage, gpu_usage, gpu_mem_usage, disk_usage],
            every=5
        )
    
    return demo

# Launch the application
if __name__ == "__main__":
    demo = create_ui()
    demo.launch(server_port=7860, inbrowser=True, share=False)