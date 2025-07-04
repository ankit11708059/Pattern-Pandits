from mcp.server.fastmcp import FastMCP

mcp = FastMCP("math")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together.
    
    Args:
        a: The first number to add
        b: The second number to add
        
    Returns:
        The sum of a and b
    """
    return a + b
