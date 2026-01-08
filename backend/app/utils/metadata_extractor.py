import os
import re
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger("MetadataExtractor")

class MetadataExtractor:
    """
    Extract metadata from academic documents
    """
    
    # Patterns
    YEAR_PATTERN = r'256[5-9]|257[0-5]'
    SEMESTER_PATTERN = r'ภาค(?:การศึกษา)?(?:ที่)?\s*([123]|ฤดูร้อน)'
    
    # Document type keywords
    DOC_TYPES = {
        'calendar': ['ปฏิทิน', 'calendar', 'academic calendar'],
        'regulation': ['ระเบียบ', 'regulation', 'reg'],
        'announcement': ['ประกาศ', 'announce'],
        'payment': ['จ่ายเงิน', 'payment', 'ค่าธรรมเนียม'],
        'registration': ['ลงทะเบียน', 'registration', 'reg']
    }
    
    def extract(self, content: str, filepath: str) -> Dict:
        """
        Extract all metadata from document
        
        Args:
            content: Full document text
            filepath: Path to document file
        
        Returns:
            Dictionary of metadata
        """
        try:
            metadata = {
                'source': filepath,
                'filename': os.path.basename(filepath),
                'academic_years': self._extract_years(content),
                'semesters': self._extract_semesters(content),
                'doc_type': self._classify_doc_type(content, filepath),
                'language': self._detect_language(content),
                'has_dates': self._has_date_info(content),
                'last_updated': self._get_file_mtime(filepath)
            }
            
            logger.debug(f"📋 Extracted metadata from {metadata['filename']}: {metadata['doc_type']}, years={metadata['academic_years']}")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Metadata extraction error for {filepath}: {e}")
            return self._default_metadata(filepath)
    
    def _extract_years(self, text: str) -> List[str]:
        """Extract academic years (Buddhist calendar)"""
        years = re.findall(self.YEAR_PATTERN, text)
        return sorted(list(set(years)), reverse=True)
    
    def _extract_semesters(self, text: str) -> List[int]:
        """Extract semester numbers"""
        matches = re.findall(self.SEMESTER_PATTERN, text)
        
        semester_map = {
            '1': 1,
            '2': 2, 
            '3': 3,
            'ฤดูร้อน': 3
        }
        
        semesters = [semester_map.get(m, 0) for m in matches if m in semester_map]
        return sorted(list(set(semesters)))
    
    def _classify_doc_type(self, content: str, filepath: str) -> str:
        """Classify document type based on content and filename"""
        filename_lower = os.path.basename(filepath).lower()
        content_sample = content[:1000].lower()
        
        # Check each document type
        for doc_type, keywords in self.DOC_TYPES.items():
            for keyword in keywords:
                if keyword.lower() in filename_lower or keyword in content_sample:
                    return doc_type
        
        return 'general'
    
    def _detect_language(self, text: str) -> str:
        """Detect primary language"""
        sample = text[:5000]
        
        # Count character types
        thai_chars = sum(1 for c in sample if '\u0e00' <= c <= '\u0e7f')
        eng_chars = sum(1 for c in sample if c.isalpha() and c.isascii())
        
        if thai_chars > eng_chars * 2:
            return 'th'
        elif eng_chars > thai_chars * 2:
            return 'en'
        else:
            return 'mixed'
    
    def _has_date_info(self, text: str) -> bool:
        """Check if document contains date information"""
        date_patterns = [
            r'\d{1,2}\s+(?:ม\.ค.|ก\.พ.|มี\.ค.|เม\.ย.|พ\.ค.|มิ\.ย.|ก\.ค.|ส\.ค.|ก\.ย.|ต\.ค.|พ\.ย.|ธ\.ค.)',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'วันที่\s+\d{1,2}'
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, text[:2000]):
                return True
        
        return False
    
    def _get_file_mtime(self, filepath: str) -> str:
        """Get file modification time"""
        try:
            mtime = os.path.getmtime(filepath)
            return datetime.fromtimestamp(mtime).isoformat()
        except:
            return datetime.now().isoformat()
    
    def _default_metadata(self, filepath: str) -> Dict:
        """Return default metadata on error"""
        return {
            'source': filepath,
            'filename': os.path.basename(filepath),
            'academic_years': [],
            'semesters': [],
            'doc_type': 'general',
            'language': 'th',
            'has_dates': False,
            'last_updated': datetime.now().isoformat()
        }

# Global singleton instance
metadata_extractor = MetadataExtractor()
