import os
import json
import logging
from zipfile import ZipFile
from dotenv import load_dotenv
from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
from adobe.pdfservices.operation.pdfjobs.jobs.extract_pdf_job import ExtractPDFJob
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_element_type import ExtractElementType
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_pdf_params import ExtractPDFParams
from adobe.pdfservices.operation.pdfjobs.result.extract_pdf_result import ExtractPDFResult
from adobe.pdfservices.operation.exception.exceptions import ServiceApiException, ServiceUsageException, SdkException

load_dotenv()

class ExtractTextInfoFromPDF:
    def __init__(self, output_path="output/ExtractTextInfoFromPDF/structuredData.json"):
        try:
            credentials = ServicePrincipalCredentials(
                        client_id=os.getenv('PDF_SERVICES_CLIENT_ID'),
                        client_secret=os.getenv('PDF_SERVICES_CLIENT_SECRET')
                    )


            with open("extractPdfInput.pdf", "rb") as file:
                input_stream = file.read()

            pdf_services = PDFServices(credentials=credentials)
            input_asset = pdf_services.upload(input_stream=input_stream, mime_type=PDFServicesMediaType.PDF)

            extract_pdf_params = ExtractPDFParams(
                elements_to_extract=[
                    ExtractElementType.TEXT,
                    ExtractElementType.TABLES,
                    ExtractElementType.FIGURES
                ],
                include_renditions=True
            )

            extract_pdf_job = ExtractPDFJob(input_asset=input_asset, extract_pdf_params=extract_pdf_params)
            location = pdf_services.submit(extract_pdf_job)
            pdf_services_response = pdf_services.get_job_result(location, ExtractPDFResult)

            result_asset: CloudAsset = pdf_services_response.get_result().get_resource()
            stream_asset: StreamAsset = pdf_services.get_content(result_asset)

            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)

            zip_path = os.path.join(output_dir, "temp_extract.zip")
            with open(zip_path, "wb") as file:
                file.write(stream_asset.get_input_stream())

            with ZipFile(zip_path, 'r') as archive:
                archive.extractall(output_dir)

            with open(os.path.join(output_dir, "structuredData.json"), "r") as json_out:
                json_data = json.load(json_out)

            with open(output_path, "w") as f:
                json.dump(json_data, f, indent=2)

            os.remove(zip_path)

        except (ServiceApiException, ServiceUsageException, SdkException) as e:
            logging.exception(f"Exception encountered while executing operation: {e}")
