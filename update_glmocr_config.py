import yaml

def update_config(config_path='glmocr/config.yaml'):
    print(f"Reading configuration from: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {config_path} not found.")
        print("Please run this script from the root director of your cloned 'glm-ocr' repository.")
        return

    # Core server settings (listen to local network requests)
    config['server']['host'] = '0.0.0.0'
    config['server']['port'] = 5002

    # Disable Maas (Zhipu AI Cloud API) - GUARANTEES ZERO EXTERNAL API CALLS
    config['pipeline']['maas']['enabled'] = False
    
    # Point SDK to local vLLM serving the GLM-OCR weights
    config['pipeline']['ocr_api']['api_host'] = 'localhost'
    config['pipeline']['ocr_api']['api_port'] = 8080
    
    # Required Outputs & Layout Engines
    config['pipeline']['result_formatter']['output_format'] = 'markdown'
    config['pipeline']['enable_layout'] = True

    # ---------------------------------------------------------
    # ADVANCED PIPELINE REASONING (Flowcharts and PPTs)
    # Intercept 'figure' bounding boxes to extract graph logics
    # ---------------------------------------------------------
    custom_prompts = {
        'text': 'Text Recognition:',
        'table': 'Table Recognition:',
        'formula': 'Formula Recognition:',
        'figure': (
            'Analyze this diagram/flowchart in extreme detail. '
            '1. Identify all distinct textual nodes or boxes. '
            '2. Explicitly describe the connections, arrows, and spatial relationships between these nodes. '
            '3. Output the structured graph logic in Markdown format.'
        )
    }
    
    # Inject into Page Loader instructions
    if 'page_loader' not in config['pipeline']:
        config['pipeline']['page_loader'] = {}
    config['pipeline']['page_loader']['task_prompt_mapping'] = custom_prompts

    # Write patched configuration back to disk
    with open(config_path, 'w') as f:
        yaml.safe_dump(config, f)
        
    print("\n[SUCCESS] Custom Flowchart Prompts & Local-Only Networking Injected!")
    print(f" - Local API Output: http://0.0.0.0:5002/glmocr/parse")
    print(f" - Image Prompts Mapped -> Local vLLM (localhost:8080)")
    print(f" - Zhipu API (MaaS) Disabled: {not config['pipeline']['maas']['enabled']}")

if __name__ == "__main__":
    update_config()
