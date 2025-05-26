import { useState, useEffect, useRef } from 'react';
import { Logo } from '../components/logo';
import axios from 'axios';

// Backend URL from environment variables
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL

// Type definitions for PDF document
interface PDF {
    id: number;
    filename: string;
    file_size: number;
    upload_date: string;
    content_type: string;
}

// Props for the Navbar component including callback functions for PDF selection
interface NavbarProps {
    onPdfSelect?: (pdf: PDF | null) => void;
    selectedPdf: PDF | null;
    setSelectedPdf?: (pdf: PDF | null) => void;
}

const Navbar: React.FC<NavbarProps> = ({ onPdfSelect, selectedPdf: externalSelectedPdf, setSelectedPdf }) => {
    const [isMobile, setIsMobile] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadResult, setUploadResult] = useState<{
        id: string;
        filename: string;
        file_size: number;
        text_preview: string;
    } | null>(null);
    const [pdfs, setPdfs] = useState<PDF[]>([]);
    
    // Handle both internal and external PDF selection state
    const [internalSelectedPdf, setInternalSelectedPdf] = useState<PDF | null>(null);
    const selectedPdf = externalSelectedPdf !== undefined ? externalSelectedPdf : internalSelectedPdf;
    const [showPdfDropdown, setShowPdfDropdown] = useState(false);

    // Fetch all available PDFs on component mount
    useEffect(() => {
        fetchPdfs();
    }, []);

    // API call to fetch all PDFs from the backend
    const fetchPdfs = () => {
        axios.get(`${BACKEND_URL}/pdfs`, { withCredentials: true })
            .then(response => {
                if (response.status === 200 && response.data) {
                    setPdfs(response.data.pdfs || []);

                    // Auto-select the first PDF if available
                    if (response.data.pdfs && response.data.pdfs.length > 0) {
                        const firstPdf = response.data.pdfs[0];
                        setInternalSelectedPdf(firstPdf);
                        if (onPdfSelect) {
                            onPdfSelect(firstPdf);
                        }
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching PDFs:', error);
            });
    };

    // Reference to the hidden file input element
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Trigger file selection dialog
    const handleUploadPDF = () => {
        // Trigger the hidden file input click
        fileInputRef.current?.click();
    }

    // Handle PDF selection from dropdown
    const handleSelectPdf = (pdf: PDF) => {
        setInternalSelectedPdf(pdf);
        if (onPdfSelect) {
            onPdfSelect(pdf);
        }
        setShowPdfDropdown(false);
    };

    // Handle file upload when a file is selected
    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        // Validate file type
        if (file.type !== 'application/pdf') {
            alert('Please select a PDF file');
            return;
        }

        try {
            setIsUploading(true);
            setUploadResult(null);

            // Prepare form data for file upload
            const formData = new FormData();
            formData.append('file', file);

            // Send file to backend API
            const response = await axios.post(`${BACKEND_URL}/upload`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                withCredentials: true,
            });

            // Store upload result data
            setUploadResult({
                id: response.data.id,
                filename: response.data.filename,
                file_size: response.data.file_size,
                text_preview: response.data.text_preview
            });

            const fileSizeFormatted = formatFileSize(response.data.file_size);

            alert(`PDF uploaded successfully: ${file.name} (${fileSizeFormatted})`);
            
            // Select the newly uploaded PDF
            setSelectedPdf && setSelectedPdf(response.data);
            
            // Refresh the PDF list
            fetchPdfs();

        } catch (error: any) {
            console.error('Error uploading PDF:', error);
            const errorMessage = error.response?.data?.detail || 'Failed to upload PDF. Please try again.';
            alert(`Upload failed: ${errorMessage}`);
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    }

    // Utility function to format file size in human-readable format
    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return bytes + ' bytes';
        else if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        else if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        else return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
    };

    // Handle responsive design and dropdown closing
    useEffect(() => {
        // Check if device is mobile based on window width
        const checkIfMobile = () => {
            setIsMobile(window.innerWidth < 720);
        };

        checkIfMobile();
        window.addEventListener('resize', checkIfMobile);

        // Close dropdown when clicking outside of it
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as HTMLElement;
            if (!target.closest('.pdf-dropdown-container')) {
                setShowPdfDropdown(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);

        return () => {
            window.removeEventListener('resize', checkIfMobile);
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    return (
        <>
            <div className="flex justify-between items-center py-5 px-6 lg:px-100 shadow-md border-gray">
                <div className="flex items-center space-x-2">
                    <Logo />
                    <div className="flex flex-col">
                        <span className="font-semibold text-2xl leading-tight font-futura-bb">planet</span>
                        <span className="text-xs leading-none ml-3">formerly <span className="text-primary font-bold">DPhi</span></span>
                    </div>
                </div>

                <div className="flex items-center space-x-3">
                    {/* PDF selection dropdown */}
                    <div className="relative pdf-dropdown-container">
                        <button
                            onClick={() => setShowPdfDropdown(!showPdfDropdown)}
                            className="flex items-center text-primary hover:underline font-semibold"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            {selectedPdf ? selectedPdf.filename : 'Select PDF'}
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>

                        {/* Dropdown menu for PDF selection */}
                        {showPdfDropdown && (
                            <div className="absolute left-0 mt-2 z-10 bg-white border rounded-md shadow-lg w-64">
                                {pdfs.length === 0 ? (
                                    <div className="px-4 py-2 text-sm text-gray-500">No PDFs available</div>
                                ) : (
                                    <ul className="py-1 max-h-60 overflow-y-auto">
                                        {pdfs.map((pdf) => (
                                            <li
                                                key={pdf.id}
                                                className="px-4 py-2 text-sm hover:bg-gray-100 cursor-pointer flex items-center justify-between"
                                                onClick={() => handleSelectPdf(pdf)}
                                            >
                                                <div className="flex items-center">
                                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                                    </svg>
                                                    <span className="truncate">{pdf.filename}</span>
                                                </div>
                                                <span className="text-xs text-gray-500">{formatFileSize(pdf.file_size)}</span>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Hidden file input for PDF upload */}
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        accept="application/pdf"
                        className="hidden"
                    />
                    
                    {/* Responsive upload button - shows different UI based on device size */}
                    {isMobile ? (
                        <div className="border rounded-lg p-3">
                            <button
                                className="w-4 h-4 rounded-full border flex items-center justify-center shadow-sm hover:bg-gray-100"
                                onClick={handleUploadPDF}
                                disabled={isUploading}
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                            </button>
                        </div>
                    ) : (
                        <button className="border rounded-lg py-2 px-11 flex items-center w-50 justify-between font-bold hover:bg-gray-100"
                            onClick={handleUploadPDF}
                            disabled={isUploading}>
                            <div
                                className="w-4 h-4 rounded-full border flex items-center justify-center shadow-sm "
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                            </div>
                            {isUploading ? "Uploading..." : "Upload PDF"}
                        </button>
                    )}
                </div>
            </div>
        </>
    );
}

export default Navbar;
