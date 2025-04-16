import os
import json
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Azure Document Intelligence setup
endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
key = os.getenv("DOCUMENT_INTELLIGENCE_KEY")
document_analysis_client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

def extract_sob_metadata(file_path):
    """Extract metadata from Schedule of Benefits (SOB) document."""
    try:
        with open(file_path, "rb") as f:
            poller = document_analysis_client.begin_analyze_document("prebuilt-layout", f)
            result = poller.result()

        # Initialize variables
        plan_name = None
        state_name = None
        found_header = False

        # Process the first page
        for line in result.pages[0].lines:
            text = line.content.strip()
            
            # Look for the header sequence
            if text == "Schedule of Benefits":
                found_header = True
                continue
            
            if found_header and text == "Harvard Pilgrim Health Care, Inc.":
                # The next line should be the plan name
                continue
            
            if found_header and not plan_name and text != "Harvard Pilgrim Health Care, Inc.":
                plan_name = text
                continue
            
            # The state name is typically in all caps
            if plan_name and text.isupper() and len(text) >= 4:
                state_name = text
                break

        return plan_name, state_name
    except Exception as e:
        print(f"Error processing SOB file {file_path}: {str(e)}")
        return None, None

def extract_sbc_table(file_path):
    """Extract Q&A table and other information from Summary of Benefits and Coverage (SBC) document."""
    try:
        print(f"\nProcessing file: {file_path}")
        with open(file_path, "rb") as f:
            poller = document_analysis_client.begin_analyze_document("prebuilt-layout", f)
            result = poller.result()

        # Initialize all data structures
        qa_data = []
        medical_events_data = []
        excluded_services = ""
        other_covered_services = ""

        # Process tables
        print(f"Found {len(result.tables)} tables")
        for table_idx, table in enumerate(result.tables):
            print(f"\nAnalyzing table {table_idx + 1}")
            
            # Build a structured representation of the table
            rows = {}
            header_cells = []
            
            # First pass: collect all cells and identify headers
            for cell in table.cells:
                row_idx = cell.row_index
                col_idx = cell.column_index
                content = cell.content.strip()
                
                if row_idx == 0:  # Header row
                    header_cells.append(content)
                
                if row_idx not in rows:
                    rows[row_idx] = {}
                rows[row_idx][col_idx] = content
            
            print(f"Table headers: {header_cells}")
            
            # Check if this is the Q&A table
            if "Important Questions" in header_cells:
                print("Found Q&A table")
                # Process Q&A table
                for row_idx in sorted(rows.keys())[1:]:  # Skip header row
                    row = rows[row_idx]
                    if len(row) >= 3:
                        question = row.get(0, "").strip()
                        answer = row.get(1, "").strip()
                        why_matters = row.get(2, "").strip()
                        
                        if question and question != "Important Questions":
                            qa_data.append({
                                "question": question,
                                "answer": answer,
                                "why_this_matters": why_matters
                            })
                print(f"Extracted {len(qa_data)} Q&A pairs")

            # Check if this is the Medical Events table
            elif "Common Medical Event" in header_cells:
                print("Found Medical Events table")
                # Process Medical Events table
                for row_idx in sorted(rows.keys())[1:]:  # Skip header row
                    row = rows[row_idx]
                    if len(row) >= 4:  # Changed from 5 to 4 as per actual table structure
                        event_data = {
                            "common_medical_event": row.get(0, "").strip(),
                            "services_you_may_need": row.get(1, "").strip(),
                            "what_you_will_pay": row.get(2, "").strip(),
                            "limitations_exceptions": row.get(3, "").strip()
                        }
                        if event_data["common_medical_event"]:  # Only add if there's an event
                            medical_events_data.append(event_data)
                print(f"Extracted {len(medical_events_data)} medical events")

            # Check if this is the excluded services table
            elif any("Services Your Plan Does NOT Cover" in cell for cell in header_cells):
                # Get all non-empty cells from the table
                all_cells = []
                for row_idx in rows:
                    all_cells.extend([v.strip() for v in rows[row_idx].values() if v.strip()])
                excluded_services = " ".join(all_cells)
                print("Found excluded services")

            # Check if this is the other covered services table
            elif any("Other Covered Services" in cell for cell in header_cells):
                # Get all non-empty cells from the table
                all_cells = []
                for row_idx in rows:
                    all_cells.extend([v.strip() for v in rows[row_idx].values() if v.strip()])
                other_covered_services = " ".join(all_cells)
                print("Found other covered services")

        result_data = {
            "qa_data": qa_data,
            "medical_events_data": medical_events_data,
            "excluded_services": excluded_services,
            "other_covered_services": other_covered_services
        }
        
        print("\nExtraction summary:")
        print(f"- QA pairs: {len(qa_data)}")
        print(f"- Medical events: {len(medical_events_data)}")
        print(f"- Excluded services: {'Found' if excluded_services else 'Not found'}")
        print(f"- Other covered services: {'Found' if other_covered_services else 'Not found'}")
        
        return result_data

    except Exception as e:
        print(f"Error processing SBC file {file_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "qa_data": [],
            "medical_events_data": [],
            "excluded_services": "",
            "other_covered_services": ""
        }

def process_document_pair(sob_path, sbc_path):
    """Process a pair of SOB and SBC documents and generate metadata JSON."""
    # Extract base filename without extension
    base_filename = os.path.splitext(os.path.basename(sbc_path))[0]
    output_path = os.path.join(os.path.dirname(sbc_path), f"{base_filename}.json")

    # Extract metadata from both documents
    plan_name, state = extract_sob_metadata(sob_path)
    sbc_data = extract_sbc_table(sbc_path)

    # Create metadata dictionary
    metadata = {
        "sob_file": os.path.basename(sob_path),
        "sbc_file": os.path.basename(sbc_path),
        "plan_name": plan_name,
        "state": state,
        **sbc_data  # Unpack all SBC data into the metadata
    }

    # Save metadata to JSON file
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Generated metadata file: {output_path}")

def main():
    data_dir = "data"
    
    # Get all SOB files
    sob_files = [f for f in os.listdir(data_dir) if f.startswith("SOB_") and f.endswith(".pdf")]
    
    # Process each SOB file and its corresponding SBC file
    for sob_file in sob_files:
        sob_path = os.path.join(data_dir, sob_file)
        sbc_file = f"SBC_{sob_file[4:]}"  # Replace SOB_ with SBC_
        sbc_path = os.path.join(data_dir, sbc_file)
        
        if os.path.exists(sbc_path):
            print(f"Processing {sob_file} and {sbc_file}...")
            process_document_pair(sob_path, sbc_path)
        else:
            print(f"Warning: No matching SBC file found for {sob_file}")

if __name__ == "__main__":
    main() 