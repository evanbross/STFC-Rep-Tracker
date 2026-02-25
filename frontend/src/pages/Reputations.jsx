import React, { useState, useEffect } from 'react';
import axios from 'axios';

const RepTable = ({ title, data, loading }) => (
  <div className="container">
    <h2>{title}</h2>
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th className="text-right">Low Limit</th>
          <th className="text-right">High Limit</th>
        </tr>
      </thead>
      <tbody>
        {loading ? (
          <tr><td colSpan="3">Loading...</td></tr>
        ) : data.length === 0 ? (
          <tr><td colSpan="3">No reputations found.</td></tr>
        ) : data.map((rep, idx) => (
          <tr key={idx}>
            <td>{rep.name}</td>
            <td className="text-right">{rep.low_limit?.toLocaleString()}</td>
            <td className="text-right">
              {rep.high_limit !== null && rep.high_limit !== undefined ? rep.high_limit.toLocaleString() : '-'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const Reputations = () => {
  const [reputationGroups, setReputationGroups] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAllReputations = async () => {
      setLoading(true);
      try {
        const response = await axios.get('/api/reputations/all');
        setReputationGroups(response.data);
      } catch (error) {
        console.error('Error loading reputations:', error);
      } finally {
        setLoading(false);
      }
    };

    loadAllReputations();
  }, []);

  return (
    <div className="reputations-page">
      <h1>Reputation Tiers</h1>
      
      {reputationGroups.map((group, idx) => (
        <RepTable key={idx} title={group.title} data={group.data} loading={loading} />
      ))}
    </div>
  );
};

export default Reputations;
