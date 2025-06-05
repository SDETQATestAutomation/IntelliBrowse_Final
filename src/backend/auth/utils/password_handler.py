"""
Password handler for secure password operations.
Provides bcrypt password hashing and strength validation functionality.
"""

import re
from typing import Dict, List, Optional
from passlib.context import CryptContext

from ...config.logging import get_logger

logger = get_logger(__name__)


class PasswordHandler:
    """
    Password handler for secure password operations.
    
    Provides bcrypt password hashing with configurable rounds and
    comprehensive password strength validation with scoring.
    """
    
    def __init__(self, bcrypt_rounds: int = 12):
        """
        Initialize password handler with bcrypt configuration.
        
        Args:
            bcrypt_rounds: Number of bcrypt rounds (default: 12 for security)
        """
        self.bcrypt_rounds = bcrypt_rounds
        self.pwd_context = CryptContext(
            schemes=["bcrypt"], 
            deprecated="auto",
            bcrypt__rounds=bcrypt_rounds
        )
        
        logger.info(
            f"Password handler initialized with {bcrypt_rounds} bcrypt rounds",
            extra={"bcrypt_rounds": bcrypt_rounds}
        )
    
    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Bcrypt hashed password
            
        Raises:
            ValueError: If password is empty or invalid
            Exception: If hashing fails
        """
        if not password or not password.strip():
            raise ValueError("Password cannot be empty")
        
        try:
            hashed = self.pwd_context.hash(password)
            
            logger.debug(
                "Password hashed successfully",
                extra={
                    "password_length": len(password),
                    "hash_algorithm": "bcrypt",
                    "hash_rounds": self.bcrypt_rounds,
                }
            )
            
            return hashed
            
        except Exception as e:
            logger.error(
                f"Password hashing failed: {str(e)}",
                extra={
                    "error": str(e),
                    "password_length": len(password) if password else 0,
                }
            )
            raise Exception(f"Password hashing failed: {str(e)}")
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against bcrypt hash.
        
        Args:
            password: Plain text password
            hashed_password: Bcrypt hashed password
            
        Returns:
            True if password matches hash, False otherwise
        """
        if not password or not hashed_password:
            logger.warning(
                "Password verification attempted with empty values",
                extra={
                    "password_empty": not bool(password),
                    "hash_empty": not bool(hashed_password),
                }
            )
            return False
        
        try:
            result = self.pwd_context.verify(password, hashed_password)
            
            logger.debug(
                f"Password verification {'successful' if result else 'failed'}",
                extra={
                    "verification_result": result,
                    "password_length": len(password),
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Password verification error: {str(e)}",
                extra={
                    "error": str(e),
                    "password_length": len(password) if password else 0,
                }
            )
            return False
    
    def validate_password_strength(self, password: str) -> Dict[str, any]:
        """
        Validate password strength with detailed feedback.
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results and feedback
        """
        if not password:
            return {
                "is_valid": False,
                "score": 0,
                "feedback": ["Password cannot be empty"],
                "requirements_met": {},
            }
        
        feedback = []
        requirements = {}
        score = 0
        
        # Length check
        min_length = 8
        max_length = 128
        if len(password) < min_length:
            feedback.append(f"Password must be at least {min_length} characters long")
            requirements["length"] = False
        elif len(password) > max_length:
            feedback.append(f"Password must not exceed {max_length} characters")
            requirements["length"] = False
        else:
            requirements["length"] = True
            score += 2
        
        # Character type checks
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password))
        
        requirements.update({
            "uppercase": has_upper,
            "lowercase": has_lower,
            "digit": has_digit,
            "special": has_special,
        })
        
        if not has_upper:
            feedback.append("Password must contain at least one uppercase letter")
        else:
            score += 1
        
        if not has_lower:
            feedback.append("Password must contain at least one lowercase letter")
        else:
            score += 1
        
        if not has_digit:
            feedback.append("Password must contain at least one digit")
        else:
            score += 1
        
        if not has_special:
            feedback.append("Password should contain at least one special character")
        else:
            score += 1
        
        # Additional strength checks
        common_patterns = self._check_common_patterns(password)
        if common_patterns:
            feedback.extend(common_patterns)
            score = max(0, score - len(common_patterns))
        
        # Bonus points for length
        if len(password) >= 12:
            score += 1
        if len(password) >= 16:
            score += 1
        
        # Calculate strength level
        if score >= 7:
            strength = "very_strong"
        elif score >= 5:
            strength = "strong"
        elif score >= 3:
            strength = "medium"
        elif score >= 2:
            strength = "weak"
        else:
            strength = "very_weak"
        
        is_valid = (
            requirements.get("length", False) and
            requirements.get("uppercase", False) and
            requirements.get("lowercase", False) and
            requirements.get("digit", False)
        )
        
        result = {
            "is_valid": is_valid,
            "score": score,
            "strength": strength,
            "feedback": feedback if feedback else ["Password meets all requirements"],
            "requirements_met": requirements,
        }
        
        logger.debug(
            f"Password strength validation completed",
            extra={
                "password_length": len(password),
                "strength": strength,
                "score": score,
                "is_valid": is_valid,
            }
        )
        
        return result
    
    def _check_common_patterns(self, password: str) -> List[str]:
        """
        Check for common weak password patterns.
        
        Args:
            password: Password to check
            
        Returns:
            List of identified weak patterns
        """
        issues = []
        
        # Check for common sequences
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):
            issues.append("Avoid sequential numbers")
        
        if re.search(r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', password.lower()):
            issues.append("Avoid sequential letters")
        
        # Check for repeated characters
        if re.search(r'(.)\1{2,}', password):
            issues.append("Avoid repeating the same character more than twice")
        
        # Check for keyboard patterns
        keyboard_patterns = ['qwerty', 'asdf', 'zxcv', '1234', 'abcd']
        for pattern in keyboard_patterns:
            if pattern in password.lower():
                issues.append(f"Avoid keyboard patterns like '{pattern}'")
        
        # Check for common words (basic check)
        common_words = ['password', 'admin', 'user', 'login', 'test']
        for word in common_words:
            if word in password.lower():
                issues.append(f"Avoid common words like '{word}'")
        
        return issues


# Global password handler instance
_password_handler: Optional[PasswordHandler] = None


def get_password_handler() -> PasswordHandler:
    """
    Get the global password handler instance.
    Uses singleton pattern for consistency.
    
    Returns:
        PasswordHandler instance
    """
    global _password_handler
    if _password_handler is None:
        _password_handler = PasswordHandler()
    return _password_handler 