"""Import Bangladesh AgroScan data pack into the shop database."""
from agroscan.shop_seed import seed_from_pack

if __name__ == "__main__":
    print(seed_from_pack())
