-- Sample Table: CustomerReviews
-- Connects directly to Northwind Products(ProductID) and Customers(CustomerID)
CREATE TABLE IF NOT EXISTS CustomerReviews (
    ReviewID INTEGER PRIMARY KEY AUTOINCREMENT,
    ProductID INTEGER NOT NULL,
    CustomerID TEXT NOT NULL,
    Rating INTEGER CHECK (Rating >= 1 AND Rating <= 5),
    Headline TEXT,
    Comment TEXT,
    ReviewDate DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (ProductID) REFERENCES Products (ProductID),
    FOREIGN KEY (CustomerID) REFERENCES Customers (CustomerID)
);

-- Sample customer reviews referencing real Northwind Products (1: Chai, 2: Chang, 3: Aniseed Syrup) and Customers (ALFKI, ANATR, ANTON)
INSERT INTO CustomerReviews (ProductID, CustomerID, Rating, Headline, Comment, ReviewDate) VALUES
(1, 'ALFKI', 5, 'Exceptional Chai aroma!', 'The flavor profile is rich and authentic. Our customers in Berlin love it.', '2025-01-15'),
(2, 'ANATR', 4, 'Crisp and refreshing Chang beer', 'Great pairing with our house sandwiches. Fast delivery.', '2025-01-18'),
(3, 'ANTON', 5, 'Best Aniseed Syrup on the market', 'Perfect consistency and sweetness for our dessert recipes.', '2025-02-02'),
(1, 'ANATR', 4, 'Consistent quality', 'Third batch reordered this month. Very reliable packaging.', '2025-02-10'),
(2, 'ALFKI', 5, 'Top tier beverage', 'Highly requested by our regulars. Will continue to order weekly.', '2025-02-14');
